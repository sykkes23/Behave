import os
import unittest
import time
from core.schema import TestSpec, TestResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from database.sqlite import init_db, save_test_result, get_test_result, update_human_override, DB_PATH

class TestPhase1(unittest.TestCase):
    def setUp(self):

        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_persistence_and_override(self):

        eval_result = EvaluationResult(
            passed=False,
            score=50.0,
            failures=[EvaluationFailure(tags=["Premature Conclusion"], root_cause="unknown", observed_behavior="observed", expected_behavior="expected", severity="Medium")],
            reasoning="Failed due to premature conclusion."
        )
        test_result = TestResult(
            run_id="test_run_123",
            test_id="diagnostic_001",
            test_version="unknown",
            ai_response="Replace the sensor.",
            evaluation=eval_result,
            metadata=ExecutionMetadata(),
            timestamp=time.time()
        )


        save_test_result(test_result)


        retrieved = get_test_result("test_run_123")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.test_id, "diagnostic_001")
        self.assertFalse(retrieved.evaluation.passed)
        self.assertIsNone(retrieved.evaluation.human_verdict)


        update_human_override("test_run_123", "PASS", "Judge misunderstood response, the AI actually recommended testing.", time.time())


        overridden = get_test_result("test_run_123")
        self.assertIsNotNone(overridden)


        self.assertFalse(overridden.evaluation.passed, "Automatic verdict should remain preserved (FAIL).")
        self.assertEqual(overridden.evaluation.human_verdict, "PASS", "Human verdict should be recorded.")
        self.assertEqual(overridden.evaluation.human_reason, "Judge misunderstood response, the AI actually recommended testing.")

if __name__ == '__main__':
    unittest.main()
