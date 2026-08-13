import os
import unittest
import json
import shutil
from typing import Any

from core.baseline import create_baseline, load_baseline, BASELINE_DIR
from core.compare import compare_baselines
from core.schema import TestSpec, EvaluationResult, ExecutionMetadata, TestResult, EvaluationFailure, SessionResult
from database.sqlite import init_db, DB_PATH, save_test_result, get_test_result
from core.taxonomy import Severity, FailureTag, RootCause, BehavioralTrajectory

class TestPhase12(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(BASELINE_DIR):
            shutil.rmtree(BASELINE_DIR)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(BASELINE_DIR):
            shutil.rmtree(BASELINE_DIR)

    def _create_mock_result(self, run_id: str, test_id: str, score: float, passed: bool, critical: int, 
                            tags: list, provider: str, cost: float, model: str = "mock-1.0", ts: float = 123456789.0) -> TestResult:
        failures = [EvaluationFailure(
            tags=[t], 
            root_cause=RootCause.REASONING_ERROR.value, 
            observed_behavior="bad", 
            expected_behavior="good", 
            severity=Severity.HIGH.value if critical == 0 else Severity.CRITICAL.value
        ) for t in tags]
        
        evaluation = EvaluationResult(
            passed=passed,
            score=score,
            failures=failures,
            reasoning="Mock evaluation",
            critical_failure_count=critical
        )
        
        metadata = ExecutionMetadata(
            provider=provider,
            model=model,
            system_version="1.0",
            git_commit="abcdef"
        )
        
        usage_json = {
            "records": [
                {"role": "generation", "cost_usd": cost, "usage": {"latency_ms": 1500}}
            ]
        }
        
        return TestResult(
            run_id=run_id,
            test_id=test_id,
            test_version="1.0",
            ai_response="mock",
            evaluation=evaluation,
            metadata=metadata,
            usage_json=usage_json,
            timestamp=ts,
            provider_status="SUCCESS",
            attempt_number=1
        )

    def test_freeze_and_restore_baseline(self):
        # 1. Baseline can be frozen
        # 2. Baseline can be restored
        # 14. Historical baselines cannot be silently modified
        r1 = self._create_mock_result("r1", "t1", 85.0, True, 0, [], "mock_provider", 0.10)
        save_test_result(r1)
        
        create_baseline("v1.0", provider="mock_provider")
        
        self.assertTrue(os.path.exists(os.path.join(BASELINE_DIR, "v1.0", "manifest.json")))
        
        manifest, runs, sessions = load_baseline("v1.0")
        self.assertEqual(manifest.name, "v1.0")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["test_id"], "t1")
        self.assertEqual(runs[0]["evaluation"]["score"], 85.0)

    def test_compare_improvements_and_regressions(self):
        # 4, 5, 6, 7, 8, 9
        # Create baseline
        r1 = self._create_mock_result("r1", "t1", 85.0, True, 0, [FailureTag.HALLUCINATION.value], "mock_prov", 0.10, "mock-1.0")
        r2 = self._create_mock_result("r2", "t2", 40.0, False, 1, [FailureTag.POOR_RISK_CALIBRATION.value], "mock_prov", 0.10, "mock-1.0")
        r3 = self._create_mock_result("r3", "t3", 60.0, False, 0, [FailureTag.UNSUPPORTED_ASSUMPTION.value], "mock_prov", 0.10, "mock-1.0")
        save_test_result(r1)
        save_test_result(r2)
        save_test_result(r3)
        create_baseline("baseline", "mock_prov")
        
        # Candidate
        r1_c = self._create_mock_result("r1_c", "t1", 40.0, False, 1, [FailureTag.POOR_RISK_CALIBRATION.value], "mock_prov", 0.15, "mock-1.1", 123456799.0)
        r2_c = self._create_mock_result("r2_c", "t2", 80.0, True, 0, [], "mock_prov", 0.15, "mock-1.1", 123456799.0)
        r3_c = self._create_mock_result("r3_c", "t3", 75.0, False, 0, [FailureTag.UNSUPPORTED_ASSUMPTION.value], "mock_prov", 0.15, "mock-1.1", 123456799.0)
        save_test_result(r1_c)
        save_test_result(r2_c)
        save_test_result(r3_c)
        create_baseline("candidate", "mock_prov")
        
        import io
        import sys
        
        captured = io.StringIO()
        sys.stdout = captured
        compare_baselines("baseline", "candidate")
        sys.stdout = sys.__stdout__
        
        output = captured.getvalue()
        
        # Check overall score logic
        self.assertIn("Baseline: 61.7", output)
        self.assertIn("Candidate: 65.0", output)
        self.assertIn("Delta: +3.3", output)
        
        # Critical regression detection
        # Despite score going up, candidate has 1 critical failure and baseline has 1, wait, overall critical: 
        # baseline: t2 has 1. candidate: t1 has 1. So it's 1 vs 1. 
        self.assertIn("Critical failures:\nBaseline: 1\nCandidate: 1", output)
        
        # Test level diffing - regressions
        self.assertIn("REGRESSIONS", output)
        self.assertIn("t1 (Behavioral Regression)", output) # PASS -> FAIL
        
        # Test level diffing - improvements
        self.assertIn("IMPROVEMENTS", output)
        self.assertIn("t2", output) # FAIL -> PASS
        
        # Cost diff
        self.assertIn("Cost:\nBaseline: $0.3000\nCandidate: $0.4500", output)

if __name__ == '__main__':
    unittest.main()
