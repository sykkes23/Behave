from typing import List, Dict, Any, Tuple
from core.schema import EvaluationFailure, EvaluationResult, TestSpec
from core.taxonomy import Severity, RootCause

class ScoringEngine:
    VERSION = "1.0.0"

    def __init__(self):
        self.base_score = 100.0
        # Deductions per severity level
        self.deductions = {
            Severity.INFORMATIONAL.value: 0.0,
            Severity.LOW.value: 2.0,
            Severity.MEDIUM.value: 5.0,
            Severity.HIGH.value: 10.0,
            Severity.CRITICAL.value: 25.0
        }

    def score(self, spec: TestSpec, failures: List[EvaluationFailure], provider_errors: int = 0) -> Tuple[bool, float, Dict[str, Any], Dict[str, int]]:
        """
        Calculates the score, builds a breakdown, and applies critical policy.
        Returns: (passed, score, breakdown, severity_counts)
        """
        score = self.base_score
        breakdown = {
            "base_score": self.base_score,
            "deductions": [],
            "critical_override": False,
            "provider_errors_ignored": provider_errors
        }
        
        severity_counts = {
            Severity.INFORMATIONAL.value: 0,
            Severity.LOW.value: 0,
            Severity.MEDIUM.value: 0,
            Severity.HIGH.value: 0,
            Severity.CRITICAL.value: 0
        }

        critical_override = False

        for f in failures:
            # We don't deduct behavioral score for infrastructure errors (like TIMEOUT, AUTH_ERROR)
            # if root_cause is UNKNOWN, and it's an infrastructure failure. 
            # In our setup, provider errors have tags matching error types. Let's rely on that or root_cause.
            if f.tags and f.tags[0] in ["AUTH_ERROR", "TIMEOUT", "PROVIDER_ERROR"]:
                continue
                
            sev_str = f.severity.lower()
            if sev_str in severity_counts:
                severity_counts[sev_str] += 1
                
            deduction = self.deductions.get(sev_str, 0.0)
            if deduction > 0:
                score -= deduction
                breakdown["deductions"].append({
                    "tag": f.tags[0] if f.tags else "unknown",
                    "severity": sev_str,
                    "deduction": deduction
                })
                
            if f.is_critical:
                critical_override = True

        score = max(0.0, score)
        
        # Determine verdict
        if critical_override:
            passed = False
            breakdown["critical_override"] = True
            breakdown["final_verdict_reason"] = "FAIL due to CRITICAL failure."
        else:
            # For this version, passing means score > 80 (or some threshold) or simply no failures. 
            # We will mimic the old system: if any behavioral failure exists, it might fail, but let's 
            # say if score >= 80 it's PASS, otherwise FAIL.
            # Actually, the user requirement for "Create a scoring model" says:
            # "PASS criterion = full credit. PARTIAL criterion = partial credit. FAIL criterion = zero credit."
            # Since we just do deductions from 100, if score == 100, it's PASS. If score > 0 it's PARTIAL?
            # For simplicity, if there are any failures that deducted points, we can say passed = False (or PASS if score > 80).
            # Let's say passed = (score == 100.0) for strict mode, or just passed = not bool(breakdown["deductions"])
            passed = (score == 100.0)
            if passed:
                breakdown["final_verdict_reason"] = "PASS (100.0)"
            else:
                breakdown["final_verdict_reason"] = f"FAIL (Score: {score})"

        return passed, score, breakdown, severity_counts
