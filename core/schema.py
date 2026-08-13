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
    confidence: Optional[float] = None
    criteria_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvaluationFailure:
    tags: List[str]          # Multi-tag taxonomy (e.g., ["unsupported_assumption"])
    root_cause: str          # Why it happened (e.g., "reasoning_error")
    observed_behavior: str
    expected_behavior: str
    severity: str

@dataclass
class EvaluationResult:
    passed: bool
    score: float
    failures: List[EvaluationFailure] = field(default_factory=list)
    reasoning: str = ""
    layer_evaluations: List[LayerEvaluation] = field(default_factory=list)
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

@dataclass
class TestResult:
    run_id: str  # Unique ID for this execution (turn or session if single-turn)
    test_id: str
    test_version: str
    ai_response: str
    evaluation: EvaluationResult
    metadata: ExecutionMetadata
    timestamp: float
    
@dataclass
class TurnResult:
    turn_id: str
    turn_number: int
    user_input: str
    ai_response: str
    evaluation: EvaluationResult
    timestamp: float

@dataclass
class SessionResult:
    session_id: str
    test_id: str
    test_version: str
    turns: List[TurnResult]
    final_evaluation: EvaluationResult
    metadata: ExecutionMetadata
    timestamp: float
