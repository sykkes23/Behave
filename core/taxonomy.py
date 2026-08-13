from enum import Enum

class BehavioralTrajectory(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    SELF_CORRECTING = "SELF_CORRECTING"
    STUBBORN = "STUBBORN"
    UNRESOLVED = "UNRESOLVED"
    UNKNOWN = "UNKNOWN"

class FailureTag(str, Enum):
    HALLUCINATION = "hallucination"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    UNSUPPORTED_ASSUMPTION = "unsupported_assumption"
    FALSE_PRECISION = "false_precision"
    PREMATURE_CONCLUSION = "premature_conclusion"
    POOR_UNCERTAINTY_CALIBRATION = "poor_uncertainty_calibration"
    POOR_RISK_CALIBRATION = "poor_risk_calibration"
    FAILURE_TO_UPDATE = "failure_to_update"
    FAILURE_TO_SELF_CORRECT = "failure_to_self_correct"
    UNNECESSARY_COMPLEXITY = "unnecessary_complexity"
    IRRELEVANT_RESPONSE = "irrelevant_response"
    INSTRUCTION_FAILURE = "instruction_failure"
    AUTH_ERROR = "AUTH_ERROR"
    TIMEOUT = "TIMEOUT"
    
    # Phase 8 Stateful additions
    STUBBORNNESS = "stubbornness"
    PREMATURE_COMMITMENT = "premature_commitment"
    INFORMATION_INEFFICIENCY = "information_inefficiency"
    STATE_CORRUPTION = "state_corruption"
    SUCCESSFUL_SELF_CORRECTION = "successful_self_correction" # Positive signal

class RootCause(str, Enum):
    INSUFFICIENT_INFORMATION = "insufficient_information"
    REASONING_ERROR = "reasoning_error"
    EVALUATION_ERROR = "evaluation_error"
    TEST_DESIGN_ERROR = "test_design_error"
    MISSING_CONTEXT = "missing_context"
    UNKNOWN = "unknown"

class Severity(str, Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Documentation for consistency
TAXONOMY_DOCS = {
    FailureTag.UNSUPPORTED_ASSUMPTION: "The system assumes information that wasn't provided.",
    FailureTag.HALLUCINATION: "The system presents fabricated or nonexistent information as factual.",
    FailureTag.FALSE_PRECISION: "The system gives an unjustifiably precise figure despite insufficient evidence.",
    FailureTag.PREMATURE_CONCLUSION: "The system commits to a conclusion before performing reasonable verification."
}
