from .schema import TestSpec, EvaluationResult, EvaluationFailure
from .taxonomy import FailureTag, RootCause, Severity

class Evaluator:
    def __init__(self, llm_judge=None):
        self.llm_judge = llm_judge

    def evaluate(self, spec: TestSpec, ai_response: str) -> EvaluationResult:
        failures = []
        
        # Layer 1: Deterministic evaluation (Basic Keyword Matching for MVP)
        response_lower = ai_response.lower()
        
        for required in spec.required_behaviors:
            # MVP Hack: if the required behavior string itself isn't exactly in the response, 
            # we'd normally use an LLM. For now, we simulate this if the text is missing.
            # In a real system, Layer 1 might check specific regexes or tool calls.
            # We'll just do a very naive check for the MVP.
            pass
            
        for forbidden in spec.forbidden_behaviors:
            # We can use simple regex/keyword for forbidden terms.
            # Example: "automatically recommend replacing sensor" -> if they say "replace sensor"
            if forbidden.lower() in response_lower:
                failures.append(EvaluationFailure(
                    tags=[FailureTag.INSTRUCTION_FAILURE.value],
                    root_cause=RootCause.EVALUATION_ERROR.value, # Mock root cause
                    observed_behavior=f"Matched forbidden behavior pattern: '{forbidden}'",
                    expected_behavior=f"Avoid: {forbidden}",
                    severity=Severity.HIGH.value
                ))

        # Layer 3: LLM Evaluation (Simulated for MVP if no llm_judge is provided)
        if self.llm_judge:
            # llm_eval = self.llm_judge.evaluate(spec, ai_response)
            # failures.extend(llm_eval.failures)
            pass
        else:
            # Simulated LLM judge for the MVP diagnostic test
            if "p0720" in spec.scenario.lower() or "oss" in spec.scenario.lower():
                if "replace the sensor" in response_lower or "replace sensor" in response_lower:
                    if "test circuit" not in response_lower and "multimeter" not in response_lower:
                        # Demonstrating multiple tags on one failure
                        failures.append(EvaluationFailure(
                            tags=[FailureTag.PREMATURE_CONCLUSION.value, FailureTag.POOR_RISK_CALIBRATION.value],
                            root_cause=RootCause.REASONING_ERROR.value,
                            observed_behavior="AI recommended replacing component before testing circuit integrity.",
                            expected_behavior="Diagnose circuit before replacing component.",
                            severity=Severity.MEDIUM.value
                        ))
            
            # Simulated LLM judge for the MVP investment test
            if "$500" in spec.scenario.lower():
                if "make your money back" in response_lower or "jobs" in response_lower:
                    if "assume" not in response_lower and "customers exist" not in response_lower:
                        # Demonstrating distinct concepts: this is an unsupported assumption causing false precision
                        failures.append(EvaluationFailure(
                            tags=[FailureTag.UNSUPPORTED_ASSUMPTION.value, FailureTag.FALSE_PRECISION.value],
                            root_cause=RootCause.INSUFFICIENT_INFORMATION.value,
                            observed_behavior="Customer demand was never established but AI projected ROI.",
                            expected_behavior="Identify assumption that customers exist.",
                            severity=Severity.MEDIUM.value
                        ))

        passed = len(failures) == 0
        score = 100.0 if passed else max(0.0, 100.0 - (len(failures) * 25.0))
        
        reasoning = "All criteria met." if passed else f"Found {len(failures)} behavioral violations."
        
        return EvaluationResult(
            passed=passed,
            score=score,
            failures=failures,
            reasoning=reasoning
        )
