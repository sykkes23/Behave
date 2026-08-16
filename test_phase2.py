import os
import unittest
import time
import sqlite3
import json
from core.schema import TestResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.taxonomy import FailureTag, RootCause, Severity
from database.sqlite import init_db, save_test_result, get_test_result, DB_PATH, update_human_override

class TestPhase2(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_multi_tag_and_persistence(self):

        eval_result = EvaluationResult(
            passed=False,
            score=75.0,
            failures=[EvaluationFailure(
                tags=[FailureTag.UNSUPPORTED_ASSUMPTION.value, FailureTag.FALSE_PRECISION.value],
                root_cause=RootCause.INSUFFICIENT_INFORMATION.value,
                observed_behavior="Assumed customer base and projected 5 jobs.",
                expected_behavior="Identify missing information.",
                severity=Severity.MEDIUM.value
            )],
            reasoning="Failed due to unsupported projection."
        )
        test_result = TestResult(
            run_id="run_phase2_001",
            test_id="investment_001",
            test_version="unknown",
            ai_response="Buy a scanner. You'll make it back in 5 jobs.",
            evaluation=eval_result,
            metadata=ExecutionMetadata(),
            timestamp=time.time()
        )


        save_test_result(test_result)


        retrieved = get_test_result("run_phase2_001")
        self.assertIsNotNone(retrieved)

        failure = retrieved.evaluation.failures[0]
        self.assertEqual(len(failure.tags), 2)
        self.assertIn("unsupported_assumption", failure.tags)
        self.assertIn("false_precision", failure.tags)
        self.assertEqual(failure.root_cause, "insufficient_information")
        self.assertEqual(failure.severity, "medium")

    def test_human_override_remains_functional(self):

        eval_result = EvaluationResult(
            passed=False,
            score=50.0,
            failures=[EvaluationFailure(
                tags=[FailureTag.HALLUCINATION.value],
                root_cause=RootCause.REASONING_ERROR.value,
                observed_behavior="Fabricated error code definition.",
                expected_behavior="Check actual OBD2 manual.",
                severity=Severity.HIGH.value
            )],
            reasoning="Failed."
        )
        test_result = TestResult(
            run_id="run_phase2_002",
            test_id="diagnostic_002",
            test_version="unknown",
            ai_response="P0720 means the turbo is broken.",
            evaluation=eval_result,
            metadata=ExecutionMetadata(),
            timestamp=time.time()
        )
        save_test_result(test_result)

        update_human_override("run_phase2_002", "PARTIAL", "Actually turbo is one of the causes in this specific model.", time.time())
        retrieved = get_test_result("run_phase2_002")

        self.assertEqual(retrieved.evaluation.human_verdict, "PARTIAL")

    def test_backward_compatibility(self):

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            old_failures_json = json.dumps([{
                "category": "Premature Conclusion",
                "observed_behavior": "Guessed the answer.",
                "expected_behavior": "Test first.",
                "severity": "Medium"
            }])
            cursor.execute('''
                INSERT INTO test_runs (
                    run_id, test_id, ai_response, auto_passed, score,
                    failures_json, reasoning, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "run_old_001", "old_test", "I guess.", False, 50.0,
                old_failures_json, "Old reason", time.time()
            ))
            conn.commit()


        retrieved = get_test_result("run_old_001")
        self.assertIsNotNone(retrieved)

        failure = retrieved.evaluation.failures[0]
        self.assertEqual(failure.tags, ["Premature Conclusion"])
        self.assertEqual(failure.root_cause, "unknown")
        self.assertEqual(failure.severity, "Medium")

if __name__ == '__main__':
    unittest.main()
