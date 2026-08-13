import json
from .schema import TestSpec, EvaluationResult, EvaluationFailure, LayerEvaluation, LayerVerdict
from .taxonomy import FailureTag, RootCause, Severity
from .judge import LLMJudge

class Evaluator:
    def __init__(self, llm_judge_provider=None):
        self.llm_judge_provider = llm_judge_provider

    def evaluate(self, spec: TestSpec, ai_response: str) -> EvaluationResult:
        layer_evaluations = []
        
        # ---------------------------------------------------------
        # Layer 1: Deterministic evaluation
        # ---------------------------------------------------------
        det_failures = []
        response_lower = ai_response.lower()
        
        for forbidden in spec.forbidden_behaviors:
            if forbidden.lower() in response_lower:
                det_failures.append(EvaluationFailure(
                    tags=[FailureTag.INSTRUCTION_FAILURE.value],
                    root_cause=RootCause.EVALUATION_ERROR.value,
                    observed_behavior=f"Matched forbidden behavior pattern: '{forbidden}'",
                    expected_behavior=f"Avoid: {forbidden}",
                    severity=Severity.HIGH.value
                ))
                
        det_verdict = LayerVerdict.FAIL if det_failures else LayerVerdict.PASS
        layer_evaluations.append(LayerEvaluation(
            layer_name="deterministic",
            verdict=det_verdict,
            failures=det_failures,
            reasoning=f"Found {len(det_failures)} deterministic violations." if det_failures else "Passed deterministic checks."
        ))

        # ---------------------------------------------------------
        # Layer 2: Rule / Evidence evaluation (Simulated)
        # ---------------------------------------------------------
        # For MVP, we simulate rule evaluation based on criteria.
        rule_failures = []
        rule_results = {}
        rule_verdict = LayerVerdict.PASS
        
        if spec.criteria:
            for criterion in spec.criteria:
                # Simulated basic string matching for rules to show separation of concerns
                # In real life, Layer 2 might run specific Python regex/parsing functions.
                if criterion.id == "verify_before_recommending" and "replace" in response_lower and "multimeter" not in response_lower:
                    rule_failures.append(EvaluationFailure(
                        tags=[FailureTag.PREMATURE_CONCLUSION.value],
                        root_cause=RootCause.REASONING_ERROR.value,
                        observed_behavior="Recommended replacement without diagnostic test.",
                        expected_behavior=criterion.description,
                        severity=Severity.MEDIUM.value
                    ))
                    rule_results[criterion.id] = {"verdict": "FAIL", "evidence": "Missing multimeter test."}
                    rule_verdict = LayerVerdict.FAIL
                else:
                    rule_results[criterion.id] = {"verdict": "PASS"}

        layer_evaluations.append(LayerEvaluation(
            layer_name="rules",
            verdict=rule_verdict,
            failures=rule_failures,
            reasoning=f"Failed {len(rule_failures)} rule criteria." if rule_failures else "Passed all rules.",
            criteria_results=rule_results
        ))

        # ---------------------------------------------------------
        # Layer 3: LLM Judge evaluation
        # ---------------------------------------------------------
        llm_failures = []
        llm_results = {}
        llm_verdict = LayerVerdict.UNCERTAIN # Default to uncertain if no LLM configured/used
        llm_reasoning = "No LLM judge configured."
        llm_metadata = {}

        if isinstance(self.llm_judge_provider, LLMJudge):
            layer_verdict, reasoning, failures, criteria_results, metadata_info = self.llm_judge_provider.evaluate(spec, ai_response)
            llm_verdict = layer_verdict
            llm_reasoning = reasoning
            llm_failures = failures
            llm_results = criteria_results
            llm_metadata = metadata_info
        else:
            # MVP Simulated semantic layer (like before, but scoped to Layer 3)
            # This allows offline testing to simulate a "Judge"
            if "p0720" in spec.scenario.lower() or "oss" in spec.scenario.lower():
                if "replace the sensor" in response_lower or "replace sensor" in response_lower:
                    if "test circuit" not in response_lower and "multimeter" not in response_lower:
                        llm_failures.append(EvaluationFailure(
                            tags=[FailureTag.PREMATURE_CONCLUSION.value, FailureTag.POOR_RISK_CALIBRATION.value],
                            root_cause=RootCause.REASONING_ERROR.value,
                            observed_behavior="AI recommended replacing component before testing circuit integrity.",
                            expected_behavior="Diagnose circuit before replacing component.",
                            severity=Severity.MEDIUM.value
                        ))
                        llm_verdict = LayerVerdict.FAIL
                        llm_reasoning = "Semantic analysis detected premature conclusion."

        # If it wasn't mocked to PASS or ERROR, and failures were added, make sure verdict aligns
        if not self.llm_judge_provider and len(llm_failures) == 0:
            llm_verdict = LayerVerdict.PASS
            llm_reasoning = "Passed semantic checks."

        layer_evaluations.append(LayerEvaluation(
            layer_name="llm_judge",
            verdict=llm_verdict,
            failures=llm_failures,
            reasoning=llm_reasoning,
            criteria_results=llm_results,
            metadata=llm_metadata
        ))

        # ---------------------------------------------------------
        # Final aggregation
        # ---------------------------------------------------------
        # The system needs to know *why* the final automatic verdict happened.
        # If any layer failed (and isn't just UNCERTAIN), the final result is FAIL.
        # UNCERTAIN doesn't automatically fail the test. ERROR fails the test.
        
        final_passed = True
        all_failures = []
        for layer in layer_evaluations:
            all_failures.extend(layer.failures)
            if layer.verdict in [LayerVerdict.FAIL, LayerVerdict.ERROR]:
                final_passed = False

        score = 100.0 if final_passed else max(0.0, 100.0 - (len(all_failures) * 25.0))
        
        # We store the unique failures across layers, or just keep them all. Let's keep them all for full auditability.
        return EvaluationResult(
            passed=final_passed,
            score=score,
            failures=all_failures,
            reasoning=f"Final automatic verdict based on {len(layer_evaluations)} layers.",
            layer_evaluations=layer_evaluations
        )
