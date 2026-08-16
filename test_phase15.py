import os
import unittest
import json
import shutil
from typing import Any

from core.schema import TestSpec, TestResult, EvaluationResult, ExecutionMetadata, EvaluationFailure, SessionResult
from database.sqlite import init_db, DB_PATH, save_test_result
from core.selector import TestSelector, SelectionStrategy

class TestPhase15(unittest.TestCase):
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

    def test_selector_determinism_and_budget(self):

        for i in range(10):
            self._create_test_file(f"t{i}.json", {
                "test_id": f"t{i}",
                "scenario": f"Test {i}",
                "test_version": "1.0",
                "domain": "reasoning",
                "status": "VALID",
                "risk_level": "high" if i % 2 == 0 else "low"
            })

        selector = TestSelector(db_path=DB_PATH, corpus_dir=self.test_dir)


        man1 = selector.select(SelectionStrategy.RANDOM, limit=5, seed=123)
        man2 = selector.select(SelectionStrategy.RANDOM, limit=5, seed=123)
        man3 = selector.select(SelectionStrategy.RANDOM, limit=5, seed=999)

        self.assertEqual([t.test_id for t in man1.selected_tests], [t.test_id for t in man2.selected_tests])
        self.assertNotEqual([t.test_id for t in man1.selected_tests], [t.test_id for t in man3.selected_tests])


        man_full = selector.select(SelectionStrategy.FULL, limit=2)
        self.assertEqual(len(man_full.selected_tests), 10)




        man_budget = selector.select(SelectionStrategy.FULL, limit=10, max_cost=0.035)
        self.assertEqual(len(man_budget.selected_tests), 3)

    def test_selector_prioritization(self):
        self._create_test_file("t_crit.json", {
            "test_id": "t_crit", "scenario": "crit test", "status": "VALID", "risk_level": "high", "domain": "auto"
        })
        self._create_test_file("t_safe.json", {
            "test_id": "t_safe", "scenario": "safe test", "status": "VALID", "risk_level": "low", "domain": "auto"
        })


        failures = [EvaluationFailure(tags=["bad"], root_cause="unknown", severity="CRITICAL", observed_behavior="b", expected_behavior="g")]
        ev = EvaluationResult(passed=False, score=0.0, failures=failures, critical_failure_count=1)
        res = TestResult(
            run_id="run_1", test_id="t_crit", test_version="1.0", ai_response="", evaluation=ev,
            metadata=ExecutionMetadata(provider="mock", model="m", system_version="1", git_commit=""),
            timestamp=1.0, usage_json={}, provider_status="SUCCESS", attempt_number=1
        )
        save_test_result(res)


        ev_safe = EvaluationResult(passed=True, score=100.0)
        res_safe = TestResult(
            run_id="run_2", test_id="t_safe", test_version="1.0", ai_response="", evaluation=ev_safe,
            metadata=ExecutionMetadata(provider="mock", model="m", system_version="1", git_commit=""),
            timestamp=1.0, usage_json={}, provider_status="SUCCESS", attempt_number=1
        )
        save_test_result(res_safe)

        selector = TestSelector(db_path=DB_PATH, corpus_dir=self.test_dir)
        man = selector.select(SelectionStrategy.BALANCED, limit=2, seed=999)
        print("SELECTED TESTS:", man.selected_tests)


        crit_score = next(s.priority_score for s in man.selected_tests if s.test_id == "t_crit")
        safe_st = next(s for s in man.selected_tests if s.test_id == "t_safe")

        self.assertEqual(crit_score, 6.0)

        self.assertIn(safe_st.priority_score, (0.0, 10.0))

if __name__ == '__main__':
    unittest.main()
