import os
import unittest
import time
from core.schema import TestSpec, TestResult, EvaluationResult, EvaluationFailure
from database.sqlite import init_db, save_test_result, get_test_result, update_human_override, DB_PATH

class TestPhase1(unittest.TestCase):
    def setUp(self):
        # Use a test DB
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_persistence_and_override(self):
        # 1. Create a dummy TestResult with an automatic FAIL
        eval_result = EvaluationResult(
            passed=False,
            score=50.0,
            failures=[EvaluationFailure("Premature Conclusion", "observed", "expected", "Medium")],
            reasoning="Failed due to premature conclusion."
        )
        test_result = TestResult(
            run_id="test_run_123",
            test_id="diagnostic_001",
            ai_response="Replace the sensor.",
            evaluation=eval_result,
            timestamp=time.time()
        )
        
        # 2. Persist the evaluation
        save_test_result(test_result)
        
        # 3. Retrieve and verify persistence (survives memory clear)
        retrieved = get_test_result("test_run_123")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.test_id, "diagnostic_001")
        self.assertFalse(retrieved.evaluation.passed)
        self.assertIsNone(retrieved.evaluation.human_verdict)
        
        # 4. Human Override
        update_human_override("test_run_123", "PASS", "Judge misunderstood response, the AI actually recommended testing.", time.time())
        
        # 5. Verify the override applied, survived restart (simulated by fetching again)
        overridden = get_test_result("test_run_123")
        self.assertIsNotNone(overridden)
        
        # The system clearly distinguishes automatic vs. human verdicts:
        self.assertFalse(overridden.evaluation.passed, "Automatic verdict should remain preserved (FAIL).")
        self.assertEqual(overridden.evaluation.human_verdict, "PASS", "Human verdict should be recorded.")
        self.assertEqual(overridden.evaluation.human_reason, "Judge misunderstood response, the AI actually recommended testing.")

if __name__ == '__main__':
    unittest.main()
