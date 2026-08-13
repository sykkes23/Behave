import os
import unittest
import json
import time
from unittest.mock import MagicMock

from core.schema import TestSpec, TurnSpec, EvaluationCriterion, SessionResult, TurnResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from core.judge import LLMJudge
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, ProviderError, ProviderErrorType
from database.sqlite import init_db, DB_PATH, save_session_result, get_session_result

class MockSessionJudgeProvider(BaseProvider):
    def __init__(self, response_json):
        super().__init__(ProviderConfig(provider_name="mock_session_judge"))
        self.response_json = response_json
        self.prompt_received = ""

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        self.prompt_received = prompt
        
        if "ERROR" in self.response_json:
            raise ProviderError(ProviderErrorType.PROVIDER_ERROR, "Simulated provider crash")
            
        return ProviderResponse(
            provider="mock_session_judge",
            model="mock_model",
            content=self.response_json,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            latency_ms=100
        )

class TestPhase9(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        
        self.spec = TestSpec(
            test_id="stateful_test_01",
            scenario="Diagnose fault.",
            turns=[
                TurnSpec(
                    user_input="The vehicle has P0720.",
                    criteria=[EvaluationCriterion(id="no_premature_commitment", description="Do not commit immediately.")]
                ),
                TurnSpec(
                    user_input="The connector looks clean.",
                    criteria=[EvaluationCriterion(id="update_hypothesis", description="Update hypothesis.")]
                )
            ]
        )
        
        self.turns = [
            TurnResult(
                turn_id="t1",
                turn_number=1,
                user_input="The vehicle has P0720.",
                ai_response="Replace sensor.",
                evaluation=EvaluationResult(passed=False, score=0.0, failures=[EvaluationFailure(tags=["premature_commitment"], root_cause="unknown", observed_behavior="replaced", expected_behavior="test", severity="medium")]),
                timestamp=0.0
            ),
            TurnResult(
                turn_id="t2",
                turn_number=2,
                user_input="The connector looks clean.",
                ai_response="Let's test resistance.",
                evaluation=EvaluationResult(passed=True, score=100.0, failures=[]),
                timestamp=0.0
            )
        ]

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_chronological_transcript_and_prompt(self):
        # 1, 2. Construct prompt chronologically
        response_json = json.dumps({
            "trajectory": "IMPROVING",
            "reasoning": "Model failed then improved.",
            "evidence_timeline": ["Turn 1 failed", "Turn 2 improved"]
        })
        provider = MockSessionJudgeProvider(response_json)
        judge = LLMJudge(provider=provider)
        
        traj, reasoning, timeline, meta = judge.evaluate_session(self.spec, self.turns)
        
        self.assertIn("--- TURN 1 ---", provider.prompt_received)
        self.assertIn("USER: The vehicle has P0720.", provider.prompt_received)
        self.assertIn("FAILURES DETECTED: premature_commitment", provider.prompt_received)
        
        self.assertEqual(traj, "IMPROVING")
        self.assertEqual(len(timeline), 2)
        
    def test_malformed_and_error(self):
        # 11, 12. Malformed JSON and Provider crash
        provider_malformed = MockSessionJudgeProvider("this is not json")
        judge_malformed = LLMJudge(provider=provider_malformed)
        traj, reasoning, timeline, meta = judge_malformed.evaluate_session(self.spec, self.turns)
        self.assertEqual(traj, "UNKNOWN")
        self.assertIn("malformed", reasoning.lower())
        
        provider_error = MockSessionJudgeProvider("ERROR")
        judge_error = LLMJudge(provider=provider_error)
        traj, reasoning, timeline, meta = judge_error.evaluate_session(self.spec, self.turns)
        self.assertEqual(traj, "UNKNOWN")
        self.assertIn("failed", reasoning.lower())

    def test_database_persistence_and_metadata(self):
        # 10. Persistence
        evaluator = Evaluator()
        
        provider = MockSessionJudgeProvider(json.dumps({
            "trajectory": "SELF_CORRECTING",
            "reasoning": "Model self corrected.",
            "evidence_timeline": ["Event 1"]
        }))
        evaluator.llm_judge_provider = LLMJudge(provider=provider)
        
        final_eval = evaluator.evaluate_session(self.spec, self.turns)
        session = SessionResult(
            session_id="sess_123",
            test_id="test",
            test_version="v1",
            turns=self.turns,
            final_evaluation=final_eval,
            metadata=ExecutionMetadata(),
            timestamp=0.0
        )
        
        save_session_result(session)
        fetched = get_session_result("sess_123")
        
        self.assertEqual(fetched.final_evaluation.trajectory, "SELF_CORRECTING")
        self.assertEqual(len(fetched.final_evaluation.evidence_timeline), 1)

    def test_human_session_override(self):
        # 9. Human override at the session level
        evaluator = Evaluator()
        provider = MockSessionJudgeProvider(json.dumps({
            "trajectory": "STUBBORN",
            "reasoning": "Bad.",
            "evidence_timeline": []
        }))
        evaluator.llm_judge_provider = LLMJudge(provider=provider)
        final_eval = evaluator.evaluate_session(self.spec, self.turns)
        
        session = SessionResult(
            session_id="sess_456",
            test_id="test",
            test_version="v1",
            turns=self.turns,
            final_evaluation=final_eval,
            metadata=ExecutionMetadata(),
            timestamp=0.0
        )
        save_session_result(session)
        
        # Override
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            # Wait, the DB schema has final_evaluation_json in test_sessions, but human_verdict is stored there via _serialize_evaluation.
            # To update it in DB directly, we'd have to parse JSON, update, re-serialize. 
            # Or just update the object and call save_session_result again (assuming it supports REPLACE or we just trust the object model).
            # test_sessions has PRIMARY KEY on session_id, so INSERT will fail if we just call save_session_result.
            # We can use INSERT OR REPLACE. Let's adjust DB or just update it via Python.
            cursor.execute('SELECT final_evaluation_json FROM test_sessions WHERE session_id = ?', ("sess_456",))
            row = cursor.fetchone()
            eval_data = json.loads(row[0])
            eval_data["human_verdict"] = "PARTIAL"
            eval_data["human_reason"] = "It wasn't that bad."
            cursor.execute('UPDATE test_sessions SET final_evaluation_json = ? WHERE session_id = ?', (json.dumps(eval_data), "sess_456"))
            conn.commit()
        finally:
            conn.close()
            
        fetched = get_session_result("sess_456")
        self.assertEqual(fetched.final_evaluation.human_verdict, "PARTIAL")
        self.assertEqual(fetched.final_evaluation.human_reason, "It wasn't that bad.")

if __name__ == '__main__':
    unittest.main()
