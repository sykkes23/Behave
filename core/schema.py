from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class TestSpec:
    test_id: str
    scenario: str
    required_behaviors: List[str] = field(default_factory=list)
    forbidden_behaviors: List[str] = field(default_factory=list)
    evaluation_criteria: List[str] = field(default_factory=list)

@dataclass
class EvaluationFailure:
    category: str
    observed_behavior: str
    expected_behavior: str
    severity: str

@dataclass
class EvaluationResult:
    passed: bool
    score: float
    failures: List[EvaluationFailure] = field(default_factory=list)
    reasoning: str = ""
    # Human Override Fields
    human_verdict: Optional[str] = None  # PASS, FAIL, PARTIAL, INVALID TEST
    human_reason: Optional[str] = None
    review_timestamp: Optional[float] = None

@dataclass
class TestResult:
    run_id: str  # Unique ID for this execution
    test_id: str
    ai_response: str
    evaluation: EvaluationResult
    timestamp: float
