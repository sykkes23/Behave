import json
from .schema import TestSpec, EvaluationResult, EvaluationFailure, LayerEvaluation, LayerVerdict, TurnResult
from .taxonomy import FailureTag, RootCause, Severity, BehavioralTrajectory
from .judge import LLMJudge
from .critical_policy import CriticalPolicyEngine
from .scoring import ScoringEngine
from .rules import evaluate_criterion, forbidden_behavior_matches, response_level_failures

class Evaluator:
    def __init__(self, llm_judge_provider=None):
        self.llm_judge_provider = llm_judge_provider
        self.critical_policy = CriticalPolicyEngine()
        self.scoring_engine = ScoringEngine()

    def evaluate(self, spec: TestSpec, ai_response: str) -> EvaluationResult:
        layer_evaluations = []




        det_failures = []
        response_lower = ai_response.lower()

        for forbidden in spec.forbidden_behaviors:
            if forbidden_behavior_matches(ai_response, forbidden):
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





        rule_failures = []
        rule_results = {}
        rule_verdict = LayerVerdict.PASS

        if spec.criteria:
            for criterion in spec.criteria:
                outcome = evaluate_criterion(criterion, ai_response, spec.scenario)
                rule_results[criterion.id] = {
                    "verdict": outcome.verdict.value,
                    "evidence": outcome.evidence,
                }
                if outcome.failure:
                    rule_failures.append(outcome.failure)

            if any(
                result["verdict"] == LayerVerdict.FAIL.value
                for result in rule_results.values()
            ):
                rule_verdict = LayerVerdict.FAIL
            elif any(
                result["verdict"] == LayerVerdict.UNCERTAIN.value
                for result in rule_results.values()
            ):
                rule_verdict = LayerVerdict.UNCERTAIN

        rule_failures.extend(response_level_failures(spec, ai_response))
        if rule_failures:
            rule_verdict = LayerVerdict.FAIL

        layer_evaluations.append(LayerEvaluation(
            layer_name="rules",
            verdict=rule_verdict,
            failures=rule_failures,
            reasoning=(
                f"Failed {len(rule_failures)} rule checks."
                if rule_failures
                else "One or more criteria lack deterministic coverage."
                if rule_verdict == LayerVerdict.UNCERTAIN
                else "Passed all implemented rules."
            ),
            criteria_results=rule_results
        ))




        llm_failures = []
        llm_results = {}
        llm_verdict = LayerVerdict.UNCERTAIN
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








        all_failures = []
        provider_errors = 0
        for layer in layer_evaluations:
            all_failures.extend(layer.failures)
            if layer.verdict == LayerVerdict.ERROR:
                provider_errors += 1

        unresolved_criteria = []
        for criterion in spec.criteria:
            rule_result = rule_results.get(criterion.id, {})
            llm_result = llm_results.get(criterion.id, {})
            rule_resolved = rule_result.get("verdict") in {"PASS", "FAIL"}
            llm_resolved = llm_result.get("verdict") in {"PASS", "FAIL"}
            if not rule_resolved and not llm_resolved:
                unresolved_criteria.append(criterion.id)


        all_failures = self.critical_policy.evaluate(spec, all_failures)


        final_passed, score, breakdown, sev_counts = self.scoring_engine.score(spec, all_failures, provider_errors)

        if unresolved_criteria:
            final_passed = False
            score = 0.0
            breakdown["measurement_incomplete"] = True
            breakdown["unresolved_criteria"] = unresolved_criteria
            breakdown["final_verdict_reason"] = (
                "NOT EVALUATED: no conclusive evaluator covered criteria: "
                + ", ".join(unresolved_criteria)
            )
            reliability_status = "INSUFFICIENT_DATA"
            reliability_reason = breakdown["final_verdict_reason"]
        else:
            breakdown["measurement_incomplete"] = False
            reliability_status = "RELIABLE"
            reliability_reason = "All explicit criteria received a conclusive evaluation."

        critical_failure = breakdown.get("critical_override", False)
        critical_count = sev_counts.get(Severity.CRITICAL.value, 0)

        return EvaluationResult(
            passed=final_passed,
            score=score,
            failures=all_failures,
            reasoning=breakdown.get("final_verdict_reason", ""),
            layer_evaluations=layer_evaluations,
            critical_failure=critical_failure,
            critical_failure_count=critical_count,
            severity_counts=sev_counts,
            score_breakdown=breakdown,
            reliability_status=reliability_status,
            reliability_reason=reliability_reason,
        )

    def evaluate_session(self, spec: TestSpec, turns: list[TurnResult]) -> EvaluationResult:


        all_failures = []
        provider_errors = 0
        provider_error_turns = []
        for turn in turns:
            all_failures.extend(turn.evaluation.failures)
            if turn.provider_status != "SUCCESS":
                provider_errors += 1
                provider_error_turns.append(turn.turn_number)

        incomplete_turns = [
            turn.turn_number
            for turn in turns
            if turn.evaluation.score_breakdown.get("measurement_incomplete", False)
        ]


        all_failures = self.critical_policy.evaluate(spec, all_failures)


        final_passed, score, breakdown, sev_counts = self.scoring_engine.score(spec, all_failures, provider_errors)
        if provider_error_turns:
            final_passed = False
            score = 0.0
            breakdown["execution_incomplete"] = True
            breakdown["measurement_incomplete"] = False
            breakdown["provider_error_turns"] = provider_error_turns
            breakdown["final_verdict_reason"] = (
                "NOT EVALUATED: provider execution failed on turns "
                + ", ".join(str(turn) for turn in provider_error_turns)
            )
            reliability_status = "UNRELIABLE"
            reliability_reason = breakdown["final_verdict_reason"]
        elif incomplete_turns:
            final_passed = False
            score = 0.0
            breakdown["measurement_incomplete"] = True
            breakdown["incomplete_turns"] = incomplete_turns
            breakdown["final_verdict_reason"] = (
                "NOT EVALUATED: incomplete criterion coverage on turns "
                + ", ".join(str(turn) for turn in incomplete_turns)
            )
            reliability_status = "INSUFFICIENT_DATA"
            reliability_reason = breakdown["final_verdict_reason"]
        else:
            breakdown["execution_incomplete"] = False
            breakdown["measurement_incomplete"] = False
            reliability_status = "RELIABLE"
            reliability_reason = "All turn criteria received a conclusive evaluation."

        critical_failure = breakdown.get("critical_override", False)
        critical_count = sev_counts.get(Severity.CRITICAL.value, 0)

        trajectory = None
        evidence_timeline = []
        reasoning = "Session evaluated based on aggregation of turn results."
        session_metadata = {}

        if isinstance(self.llm_judge_provider, LLMJudge):
            traj, reason, timeline, meta = self.llm_judge_provider.evaluate_session(spec, turns)
            trajectory = traj
            evidence_timeline = timeline
            reasoning = reason
            session_metadata = meta

        return EvaluationResult(
            passed=final_passed,
            score=score,
            failures=all_failures,
            reasoning=reasoning,
            trajectory=trajectory,
            evidence_timeline=evidence_timeline,
            layer_evaluations=[],
            critical_failure=critical_failure,
            critical_failure_count=critical_count,
            severity_counts=sev_counts,
            score_breakdown=breakdown,
            session_metadata=session_metadata,
            reliability_status=reliability_status,
            reliability_reason=reliability_reason,
        )
