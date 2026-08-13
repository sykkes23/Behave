import json
import time
import uuid
from .schema import TestSpec, TestResult
from .evaluator import Evaluator
from models.base import BaseAIModel

class TestRunner:
    def __init__(self, ai_model: BaseAIModel, evaluator: Evaluator):
        self.ai_model = ai_model
        self.evaluator = evaluator

    def run_test(self, spec: TestSpec) -> TestResult:
        print(f"Running Test: {spec.test_id}...")
        
        # 1. Send scenario to AI
        print(" -> Generating AI response...")
        ai_response = self.ai_model.generate_response(spec.scenario)
        
        # 2. Evaluate response
        print(" -> Evaluating response...")
        evaluation = self.evaluator.evaluate(spec, ai_response)
        
        # 3. Create Result
        result = TestResult(
            run_id=str(uuid.uuid4()),
            test_id=spec.test_id,
            ai_response=ai_response,
            evaluation=evaluation,
            timestamp=time.time()
        )
        
        return result

    def print_report(self, result: TestResult):
        print("\n" + "="*50)
        print(f"TEST REPORT: {result.test_id} (Run ID: {result.run_id})")
        print("="*50)
        print(f"Automatic Verdict: {'PASS' if result.evaluation.passed else 'FAIL'}")
        print(f"Score:             {result.evaluation.score}")
        
        if result.evaluation.human_verdict:
            print(f"Human Verdict:     {result.evaluation.human_verdict}")
            print(f"Human Reason:      {result.evaluation.human_reason}")

        print("\nAI Response:")
        print(f'"{result.ai_response}"')
        print("\nEvaluation Evidence:")
        print(f"Reasoning: {result.evaluation.reasoning}")
        
        if not result.evaluation.passed and result.evaluation.failures:
            print("\nFailures Detected:")
            for f in result.evaluation.failures:
                tags = ", ".join(f.tags) if hasattr(f, 'tags') else "unknown"
                root_cause = getattr(f, 'root_cause', 'unknown')
                print(f"  - Tags: {tags}")
                print(f"    Root Cause: {root_cause}")
                print(f"    Severity: {f.severity}")
                print(f"    Expected: {f.expected_behavior}")
                print(f"    Observed: {f.observed_behavior}\n")
        print("="*50 + "\n")
