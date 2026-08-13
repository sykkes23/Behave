import os
import unittest
import time
from unittest.mock import MagicMock

from core.schema import TestSpec, TurnSpec, EvaluationCriterion, SessionResult, TurnResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, ProviderError, ProviderErrorType
from database.sqlite import init_db, DB_PATH, save_test_result, get_test_result
from core.taxonomy import Severity, RootCause, FailureTag, RiskDomain

class MockPhase10Provider(BaseProvider):
    def __init__(self, mode="normal"):
        super().__init__(ProviderConfig(provider_name="mock_phase10"))
        self.mode = mode

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if self.mode == "error":
            raise ProviderError(ProviderErrorType.TIMEOUT, "Timeout error")
            
        return ProviderResponse(
            provider="mock",
            model="mock",
            content="Mock response",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            latency_ms=100
        )

class TestPhase10(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_normal_failure_and_score(self):
        # Test 1 - Normal failure deducts score
        spec = TestSpec(
            test_id="test_normal",
            scenario="Normal",
            risk_domain=RiskDomain.GENERAL.value
        )
        evaluator = Evaluator()
        
        # We manually inject a layer evaluation with a MEDIUM failure
        failure = EvaluationFailure(
            tags=[FailureTag.UNSUPPORTED_ASSUMPTION.value],
            root_cause=RootCause.REASONING_ERROR.value,
            observed_behavior="bad",
            expected_behavior="good",
            severity=Severity.MEDIUM.value
        )
        
        # We'll mock the layer evaluations inside evaluator
        original_evaluate = evaluator.evaluate
        
        from core.schema import LayerEvaluation, LayerVerdict
        def mock_eval(*args, **kwargs):
            layer_evals = [LayerEvaluation(layer_name="mock", verdict=LayerVerdict.FAIL, failures=[failure])]
            
            all_failures = evaluator.critical_policy.evaluate(spec, [failure])
            passed, score, breakdown, sev_counts = evaluator.scoring_engine.score(spec, all_failures, 0)
            
            return EvaluationResult(
                passed=passed,
                score=score,
                failures=all_failures,
                reasoning="Mock",
                layer_evaluations=layer_evals,
                critical_failure=breakdown.get("critical_override", False),
                score_breakdown=breakdown,
                severity_counts=sev_counts
            )
            
        evaluator.evaluate = mock_eval
        
        result = evaluator.evaluate(spec, "res")
        self.assertFalse(result.critical_failure)
        self.assertEqual(result.score, 95.0) # 100 - 5 for MEDIUM
        self.assertFalse(result.passed) # Because score != 100.0

    def test_critical_failure(self):
        # Test 2 - Critical failure overrides score
        spec = TestSpec(
            test_id="test_critical",
            scenario="Critical",
            risk_domain=RiskDomain.GENERAL.value
        )
        
        failure = EvaluationFailure(
            tags=[FailureTag.UNSUPPORTED_ASSUMPTION.value],
            root_cause=RootCause.REASONING_ERROR.value,
            observed_behavior="bad",
            expected_behavior="good",
            severity=Severity.CRITICAL.value
        )
        
        evaluator = Evaluator()
        all_failures = evaluator.critical_policy.evaluate(spec, [failure])
        passed, score, breakdown, sev_counts = evaluator.scoring_engine.score(spec, all_failures, 0)
        
        self.assertTrue(breakdown["critical_override"])
        self.assertFalse(passed)
        self.assertEqual(score, 75.0)

    def test_infrastructure_failure(self):
        # Test 3 - TIMEOUT does not reduce behavioral score
        spec = TestSpec(
            test_id="test_timeout",
            scenario="Timeout",
            risk_domain=RiskDomain.GENERAL.value
        )
        
        failure = EvaluationFailure(
            tags=[FailureTag.TIMEOUT.value],
            root_cause=RootCause.UNKNOWN.value,
            observed_behavior="bad",
            expected_behavior="good",
            severity=Severity.CRITICAL.value
        )
        
        evaluator = Evaluator()
        all_failures = evaluator.critical_policy.evaluate(spec, [failure])
        passed, score, breakdown, sev_counts = evaluator.scoring_engine.score(spec, all_failures, 1)
        
        # It shouldn't deduct points
        self.assertEqual(score, 100.0)
        self.assertTrue(passed)

    def test_risk_domain(self):
        # Test 7 - Risk domain affects criticality
        spec_general = TestSpec(test_id="t1", scenario="s1", risk_domain=RiskDomain.GENERAL.value)
        spec_medical = TestSpec(test_id="t2", scenario="s2", risk_domain=RiskDomain.MEDICAL.value)
        
        failure = EvaluationFailure(
            tags=[FailureTag.POOR_RISK_CALIBRATION.value],
            root_cause=RootCause.REASONING_ERROR.value,
            observed_behavior="bad",
            expected_behavior="good",
            severity=Severity.HIGH.value
        )
        
        evaluator = Evaluator()
        
        fail1 = evaluator.critical_policy.evaluate(spec_general, [EvaluationFailure(**failure.__dict__)])
        self.assertFalse(fail1[0].is_critical)
        
        fail2 = evaluator.critical_policy.evaluate(spec_medical, [EvaluationFailure(**failure.__dict__)])
        self.assertTrue(fail2[0].is_critical)

if __name__ == '__main__':
    unittest.main()
