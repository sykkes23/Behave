import os
import unittest
import json
import shutil
from typing import Any

from core.schema import TestResult, EvaluationResult, ExecutionMetadata, EvaluationFailure, LayerEvaluation, LayerVerdict
from core.reliability import MeasurementIntegrity, MeasurementReliability
from database.sqlite import init_db, DB_PATH, save_test_result, update_human_override

class TestPhase16(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_measurement_integrity(self):
        mi = MeasurementIntegrity()


        eval1 = EvaluationResult(passed=True, score=100.0, layer_evaluations=[
            LayerEvaluation(layer_name="rules", verdict=LayerVerdict.PASS),
            LayerEvaluation(layer_name="llm_judge", verdict=LayerVerdict.PASS, confidence="HIGH")
        ])
        res1 = mi.assess_evaluation(eval1)
        self.assertEqual(res1["status"], MeasurementReliability.RELIABLE.value)


        eval2 = EvaluationResult(passed=False, score=50.0, layer_evaluations=[
            LayerEvaluation(layer_name="rules", verdict=LayerVerdict.PASS),
            LayerEvaluation(layer_name="llm_judge", verdict=LayerVerdict.FAIL)
        ])
        res2 = mi.assess_evaluation(eval2)
        self.assertEqual(res2["status"], MeasurementReliability.QUESTIONABLE.value)


        eval3 = EvaluationResult(passed=False, score=0.0, human_verdict="PASS", layer_evaluations=[
            LayerEvaluation(layer_name="llm_judge", verdict=LayerVerdict.FAIL)
        ])
        res3 = mi.assess_evaluation(eval3)
        self.assertEqual(res3["status"], MeasurementReliability.UNRELIABLE.value)

    def test_generate_report(self):

        eval_res = EvaluationResult(passed=False, score=50.0, layer_evaluations=[
            LayerEvaluation(layer_name="rules", verdict=LayerVerdict.PASS),
            LayerEvaluation(layer_name="llm_judge", verdict=LayerVerdict.FAIL)
        ])
        tr1 = TestResult(run_id="run_1", test_id="t1", test_version="1.0", ai_response="",
                         evaluation=eval_res, metadata=ExecutionMetadata("m","m","1",""), timestamp=1.0, attempt_number=1)
        save_test_result(tr1)


        tr2 = TestResult(run_id="run_2", test_id="t2", test_version="1.0", ai_response="",
                         evaluation=EvaluationResult(passed=False, score=0.0), metadata=ExecutionMetadata("m","m","1",""), timestamp=1.0, attempt_number=1)
        save_test_result(tr2)
        update_human_override("run_2", "PASS", "Wrongly failed", 2.0)

        mi = MeasurementIntegrity()
        report = mi.generate_report()

        self.assertEqual(report["total_evaluations"], 2)
        self.assertEqual(report["status_counts"][MeasurementReliability.QUESTIONABLE.value], 1)
        self.assertEqual(report["status_counts"][MeasurementReliability.UNRELIABLE.value], 1)
        self.assertEqual(report["human_override_stats"]["total_reviewed"], 1)
        self.assertEqual(report["human_override_stats"]["total_overridden"], 1)
        self.assertEqual(report["human_override_stats"]["FAIL_to_PASS"], 1)



        ambig_tids = [at["test_id"] for at in report["ambiguous_tests"]]
        self.assertIn("t1", ambig_tids)
        self.assertIn("t2", ambig_tids)

    def test_calibration_regression_gate(self):
        mi = MeasurementIntegrity()
        cal = mi.calibrate("mock", "mock")
        self.assertIn("CALIBRATION REGRESSION", cal["status"])
        self.assertLess(cal["raw_agreement"], cal["previous_raw_agreement"])

if __name__ == '__main__':
    unittest.main()
