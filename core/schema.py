from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

@dataclass
class EvaluationCriterion:
    id: str
    description: str

@dataclass
class TurnSpec:
    user_input: str
    criteria: List[EvaluationCriterion] = field(default_factory=list)
    expected_behavior: str = ""

@dataclass
class TestSpec:
    test_id: str
    scenario: str
    test_version: str = "unknown"
    turns: List[TurnSpec] = field(default_factory=list)
    # Legacy fields for backward compatibility with older single-turn tests
    criteria: List[EvaluationCriterion] = field(default_factory=list)
    required_behaviors: List[str] = field(default_factory=list)
    forbidden_behaviors: List[str] = field(default_factory=list)
    evaluation_criteria: List[str] = field(default_factory=list)
    # Phase 13 Corpus Management fields
    domain: str = "general"
    risk_domain: str = "GENERAL"
    risk_level: str = "LOW"
    principles: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: str = "VALID" # VALID, INVALID, DEPRECATED, EXPERIMENTAL
    
    # Phase 14 Lineage fields
    origin: str = "manual"
    parent_test: Optional[str] = None
    parent_version: Optional[str] = None
    generation_reason: Optional[str] = None
    mutation_strategy: Optional[str] = None
    duplicate_flag: bool = False

class LayerVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    ERROR = "ERROR"

@dataclass
class LayerEvaluation:
    layer_name: str
    verdict: LayerVerdict
    failures: List['EvaluationFailure'] = field(default_factory=list)
    reasoning: str = ""
    confidence: Any = None # Support float or str (HIGH, MEDIUM, LOW)
    criteria_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvaluationFailure:
    tags: List[str]          # Multi-tag taxonomy (e.g., ["unsupported_assumption"])
    root_cause: str          # Why it happened (e.g., "reasoning_error")
    observed_behavior: str
    expected_behavior: str
    severity: str
    is_critical: bool = False
    
class MeasurementReliability(str, Enum):
    RELIABLE = "RELIABLE"
    QUESTIONABLE = "QUESTIONABLE"
    UNRELIABLE = "UNRELIABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

@dataclass
class EvaluationResult:
    passed: bool
    score: float
    failures: List[EvaluationFailure] = field(default_factory=list)
    reasoning: str = ""
    layer_evaluations: List[LayerEvaluation] = field(default_factory=list)
    # Session-level holistic fields
    trajectory: Optional[str] = None
    evidence_timeline: List[str] = field(default_factory=list)
    
    # New Phase 10 Scoring Fields
    critical_failure: bool = False
    critical_failure_count: int = 0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    session_metadata: Dict[str, Any] = field(default_factory=dict)

    # Phase 16 Reliability Status
    reliability_status: str = "INSUFFICIENT_DATA"
    reliability_reason: str = ""
    
    # Human Override Fields
    human_verdict: Optional[str] = None  # PASS, FAIL, PARTIAL, INVALID TEST
    human_reason: Optional[str] = None
    review_timestamp: Optional[float] = None

@dataclass
class ExecutionMetadata:
    system_version: str = "v0.1.0"
    git_commit: str = "unknown"
    git_dirty: bool = False
    provider: str = "unknown"
    model: str = "mock"
    model_version: str = "unknown"
    system_prompt_hash: str = "unknown"
    configuration_hash: str = "unknown"
    evaluation_engine_version: str = "0.1"
    # Judge Metadata
    judge_provider: str = "unknown"
    judge_model: str = "unknown"
    judge_prompt_hash: str = "unknown"
    
    # Phase 10 Metadata
    scoring_policy_version: str = "1.0.0"
    critical_policy_version: str = "1.0.0"
    
    # Phase 11 Metadata
    pricing_version: str = "2026-08-01"
    usage_schema_version: str = "1.0.0"

@dataclass
class TestResult:
    run_id: str  # Unique ID for this execution (turn or session if single-turn)
    test_id: str
    test_version: str
    ai_response: str
    evaluation: EvaluationResult
    metadata: ExecutionMetadata
    timestamp: float
    
    # Phase 11 tracking
    usage_json: Dict[str, Any] = field(default_factory=dict)
    provider_status: str = "SUCCESS"
    attempt_number: int = 1
    
@dataclass
class TurnResult:
    turn_id: str
    turn_number: int
    user_input: str
    ai_response: str
    evaluation: EvaluationResult
    timestamp: float
    
    # Phase 11 tracking
    usage_json: Dict[str, Any] = field(default_factory=dict)
    provider_status: str = "SUCCESS"
    attempt_number: int = 1

@dataclass
class SessionResult:
    session_id: str
    test_id: str
    test_version: str
    turns: List[TurnResult]
    final_evaluation: EvaluationResult
    metadata: ExecutionMetadata
    timestamp: float
    
    # Phase 11 tracking
    usage_json: Dict[str, Any] = field(default_factory=dict)
    provider_status: str = "SUCCESS"
    attempt_number: int = 1

class FinalDecision(str, Enum):
    DEPLOY = "DEPLOY"
    CONDITIONAL = "CONDITIONAL"
    REGRESSION = "REGRESSION"
    BLOCKED = "BLOCKED"

@dataclass
class DecisionPolicy:
    version: str = "1.0"
    max_cost_increase_pct: float = 20.0
    max_latency_increase_pct: float = 10.0
    allow_critical_regression: bool = False
    require_behavioral_improvement: bool = True

@dataclass
class ExperimentDefinition:
    experiment_id: str
    hypothesis: str
    baseline: str
    candidate: str
    corpus_version: str = "latest"
    selection_policy: str = "FULL"
    evaluator_version: str = "1.0"
    judge_version: str = "1.0"
    scoring_policy: str = "1.0"
    statistics_policy: str = "1.0"
    budget: float = 10.0
    stopping_rule: str = "completion"
    decision_policy: DecisionPolicy = field(default_factory=DecisionPolicy)
    
    # Execution tracking
    status: str = "PLANNED" # PLANNED, RUNNING, COMPLETED, FAILED
    results_json: Optional[str] = None
    final_decision: Optional[FinalDecision] = None
    created_at: float = 0.0
    completed_at: Optional[float] = None
