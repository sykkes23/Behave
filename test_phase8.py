import os
import unittest
import time
from unittest.mock import MagicMock

from core.schema import TestSpec, TurnSpec, EvaluationCriterion, SessionResult, TurnResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, ProviderError, ProviderErrorType, UsageMetrics
from database.sqlite import init_db, DB_PATH, save_test_result, get_test_result, save_session_result, get_session_result

class MockStatefulProvider(BaseProvider):
    def __init__(self):
        super().__init__(ProviderConfig(provider_name="mock_stateful"))
        self.history_received = []

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        self.history_received = list(history) if history else []


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
            content=f"Response to: {prompt}",
            usage=UsageMetrics(input_tokens=10, output_tokens=10, total_tokens=20, latency_ms=100)
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

        result = self.runner.run_session(self.spec)

        self.assertEqual(result.test_id, "stateful_test_01")
        self.assertIsNotNone(result.session_id)
        self.assertEqual(len(result.turns), 3)


        turn_ids = set(t.turn_id for t in result.turns)
        self.assertEqual(len(turn_ids), 3)


        self.assertEqual(result.turns[0].turn_number, 1)
        self.assertEqual(result.turns[1].turn_number, 2)
        self.assertEqual(result.turns[2].turn_number, 3)



        self.assertEqual(len(self.provider.history_received), 5)
        self.assertEqual(self.provider.history_received[0]["content"], "Diagnose fault.")
        self.assertEqual(self.provider.history_received[1]["content"], "The vehicle has P0720.")
        self.assertEqual(self.provider.history_received[2]["content"], "Response to: The vehicle has P0720.")


        self.assertIsNotNone(result.final_evaluation)
        self.assertTrue(hasattr(result.final_evaluation, "passed"))


        self.assertEqual(result.turns[0].ai_response, "Response to: The vehicle has P0720.")
        self.assertEqual(result.turns[2].ai_response, "Response to: Resistance measures 0 ohms.")

    def test_provider_error_during_turn(self):

        spec_error = TestSpec(
            test_id="error_test",
            scenario="test",
            turns=[TurnSpec(user_input="trigger error")]
        )
        result = self.runner.run_session(spec_error)
        self.assertEqual(len(result.turns), 1)
        self.assertFalse(result.turns[0].evaluation.passed)
        self.assertEqual(result.turns[0].provider_status, "AUTH_ERROR")
        self.assertIn("AUTH_ERROR", [f.tags[0] for f in result.turns[0].evaluation.failures])
        self.assertFalse(result.final_evaluation.passed)

    def test_database_persistence_and_human_override(self):

        session = self.runner.run_session(self.spec)
        save_session_result(session)


        fetched = get_session_result(session.session_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.session_id, session.session_id)
        self.assertEqual(len(fetched.turns), 3)


        turn_id_to_override = fetched.turns[0].turn_id


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


        fetched2 = get_session_result(session.session_id)
        self.assertEqual(fetched2.turns[0].evaluation.human_verdict, "FAIL")
        self.assertEqual(fetched2.turns[0].evaluation.human_reason, "Terrible answer")

if __name__ == '__main__':
    unittest.main()
