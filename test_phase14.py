import os
import unittest
import json
import shutil
from typing import Any

from core.schema import TestSpec, TestResult, EvaluationResult, ExecutionMetadata, EvaluationFailure
from database.sqlite import init_db, DB_PATH, save_test_result
from core.miner import FailureMiner

class TestPhase14(unittest.TestCase):
    def setUp(self):
        self.test_dir = "temp_tests"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def _create_test_file(self, filename: str, content: dict):
        with open(os.path.join(self.test_dir, filename), "w") as f:
            json.dump(content, f, indent=2)

    def test_failure_mining_and_generation(self):

        self._create_test_file("t1.json", {
            "test_id": "t1",
            "scenario": "Original test scenario.",
            "test_version": "1.0",
            "domain": "reasoning",
            "status": "VALID",
            "tags": ["some_tag"]
        })


        failures = [EvaluationFailure(
            tags=["unsupported_assumption"],
            root_cause="insufficient_information",
            observed_behavior="bad",
            expected_behavior="good",
            severity="high"
        )]

        evaluation = EvaluationResult(
            passed=False,
            score=40.0,
            failures=failures,
            reasoning="Mock evaluation",
            critical_failure_count=0
        )

        res = TestResult(
            run_id="run_1",
            test_id="t1",
            test_version="1.0",
            ai_response="mock",
            evaluation=evaluation,
            metadata=ExecutionMetadata(provider="mock", model="mock", system_version="1.0", git_commit=""),
            timestamp=123.0,
            usage_json={"records": []},
            provider_status="SUCCESS",
            attempt_number=1
        )
        save_test_result(res)

        miner = FailureMiner(db_path=DB_PATH, corpus_dir=self.test_dir)
        stats = miner.analyze_failures()


        self.assertIn("unsupported_assumption", stats["tags"])
        self.assertEqual(stats["tags"]["unsupported_assumption"], 1)
        self.assertIn("insufficient_information", stats["root_causes"])
        self.assertIn("t1", stats["affected_tests"]["unsupported_assumption"])


        variants = miner.generate_variant("unsupported_assumption", count=2)

        self.assertEqual(len(variants), 2)
        for v in variants:
            self.assertEqual(v.status, "EXPERIMENTAL")
            self.assertEqual(v.origin, "failure_mining")
            self.assertEqual(v.parent_test, "t1")
            self.assertEqual(v.generation_reason, "unsupported_assumption")
            self.assertTrue(v.test_id.startswith("t1_variant_"))
            self.assertTrue(v.scenario.startswith("[Mutated: "))

if __name__ == '__main__':
    unittest.main()
