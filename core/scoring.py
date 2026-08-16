from typing import List, Dict, Any, Tuple
from core.schema import EvaluationFailure, EvaluationResult, TestSpec
from core.taxonomy import Severity, RootCause

class ScoringEngine:
    VERSION = "1.0.0"

    def __init__(self):
        self.base_score = 100.0

        self.deductions = {
            Severity.INFORMATIONAL.value: 0.0,
            Severity.LOW.value: 2.0,
            Severity.MEDIUM.value: 5.0,
            Severity.HIGH.value: 10.0,
            Severity.CRITICAL.value: 25.0
        }

    def score(self, spec: TestSpec, failures: List[EvaluationFailure], provider_errors: int = 0) -> Tuple[bool, float, Dict[str, Any], Dict[str, int]]:

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


        if critical_override:
            passed = False
            breakdown["critical_override"] = True
            breakdown["final_verdict_reason"] = "FAIL due to CRITICAL failure."
        else:








            passed = (score == 100.0)
            if passed:
                breakdown["final_verdict_reason"] = "PASS (100.0)"
            else:
                breakdown["final_verdict_reason"] = f"FAIL (Score: {score})"

        return passed, score, breakdown, severity_counts
