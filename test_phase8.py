import os
import unittest
import time
from unittest.mock import MagicMock

from core.schema import TestSpec, TurnSpec, EvaluationCriterion, SessionResult, TurnResult, EvaluationResult, EvaluationFailure
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, ProviderError, ProviderErrorType
from database.sqlite import init_db, DB_PATH, save_session_result, get_session_result

class MockStatefulProvider(BaseProvider):
    def __init__(self):
        super().__init__(ProviderConfig(provider_name="mock_stateful"))
        self.history_received = []

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        self.history_received = list(history) if history else []
        
        # Simulate behavioral responses based on prompts
        if "P0720" in prompt:
            content = "Replace the OSS sensor immediately."
        elif "clean" in prompt:
            content = "Okay, if it's clean, check resistance."
        elif "0 ohms" in prompt:
            content = "That means there is a short circuit. My previous diagnosis was wrong."
        elif "error" in prompt:
            raise ProviderError(ProviderErrorType.AUTH_ERROR, "Mock provider error")
        else:
            content = "Generic response."
            
        return ProviderResponse(
            provider="mock_stateful",
            model="mock",
            content=content,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            latency_ms=100
        )

class TestPhase8(unittest.TestCase):
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
                ),
                TurnSpec(
                    user_input="Resistance measures 0 ohms.",
                    criteria=[EvaluationCriterion(id="self_correct", description="Identify short.")]
                )
            ]
        )
        self.provider = MockStatefulProvider()
        self.evaluator = Evaluator()
        self.runner = TestRunner(provider=self.provider, evaluator=self.evaluator)

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_multi_turn_execution_and_context_preservation(self):
        # Tests 1, 2, 3, 4, 5, 6, 7, 10, 11
        result = self.runner.run_session(self.spec)
        
        self.assertEqual(result.test_id, "stateful_test_01")
        self.assertIsNotNone(result.session_id)
        self.assertEqual(len(result.turns), 3)
        
        # Turn IDs should be independent
        turn_ids = set(t.turn_id for t in result.turns)
        self.assertEqual(len(turn_ids), 3)
        
        # Turn ordering
        self.assertEqual(result.turns[0].turn_number, 1)
        self.assertEqual(result.turns[1].turn_number, 2)
        self.assertEqual(result.turns[2].turn_number, 3)
        
        # Context preservation: By the 3rd turn, history should have 1 scenario + (Turn 1 Q&A) + (Turn 2 Q&A) = 5 messages
        # Context preservation: By the 3rd turn, history received by generate_response should have 1 scenario + (Turn 1 Q&A) + (Turn 2 Q&A) = 5 messages
        self.assertEqual(len(self.provider.history_received), 5)
        self.assertEqual(self.provider.history_received[0]["content"], "Diagnose fault.")
        self.assertEqual(self.provider.history_received[1]["content"], "The vehicle has P0720.")
        self.assertEqual(self.provider.history_received[2]["content"], "Replace the OSS sensor immediately.")
        
        # Evaluations exist for each turn and overall session
        self.assertIsNotNone(result.final_evaluation)
        self.assertTrue(hasattr(result.final_evaluation, "passed"))
        
        # Check specific behaviors modeled
        self.assertEqual(result.turns[0].ai_response, "Replace the OSS sensor immediately.")
        self.assertEqual(result.turns[2].ai_response, "That means there is a short circuit. My previous diagnosis was wrong.")

    def test_provider_error_during_turn(self):
        # 17. Provider errors during a turn
        spec_error = TestSpec(
            test_id="error_test",
            scenario="test",
            turns=[TurnSpec(user_input="trigger error")]
        )
        result = self.runner.run_session(spec_error)
        
        # Turn should have failed with the error
        self.assertFalse(result.turns[0].evaluation.passed)
        self.assertIn("AUTH_ERROR", [f.tags[0] for f in result.turns[0].evaluation.failures])
        self.assertFalse(result.final_evaluation.passed)
        
    def test_database_persistence_and_human_override(self):
        # 14, 15, 16. DB persistence and human override on an individual turn
        session = self.runner.run_session(self.spec)
        save_session_result(session)
        
        # Fetch from DB
        fetched = get_session_result(session.session_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.session_id, session.session_id)
        self.assertEqual(len(fetched.turns), 3)
        
        # Apply human override to the first turn
        turn_id_to_override = fetched.turns[0].turn_id
        
        # Direct DB update (simulate UI override)
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE test_turns 
                SET human_verdict = ?, human_reason = ?, review_timestamp = ?
                WHERE turn_id = ?
            ''', ("FAIL", "Terrible answer", time.time(), turn_id_to_override))
            conn.commit()
        finally:
            conn.close()
            
        # Re-fetch
        fetched2 = get_session_result(session.session_id)
        self.assertEqual(fetched2.turns[0].evaluation.human_verdict, "FAIL")
        self.assertEqual(fetched2.turns[0].evaluation.human_reason, "Terrible answer")

if __name__ == '__main__':
    unittest.main()
