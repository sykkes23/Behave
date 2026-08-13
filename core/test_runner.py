import json
import time
import uuid
from .schema import TestSpec, TestResult, ExecutionMetadata
from .metadata import get_git_info, hash_string, hash_dict
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
        
        # 3. Build Metadata
        git_commit, git_dirty = get_git_info()
        # Mock configuration for now (to demonstrate hashing)
        dummy_config = {"temperature": 0.7, "GEMINI_API_KEY": "secret123"}
        
        metadata = ExecutionMetadata(
            git_commit=git_commit,
            git_dirty=git_dirty,
            system_prompt_hash=hash_string("You are a helpful automotive assistant."), # Mock system prompt
            configuration_hash=hash_dict(dummy_config)
        )
        
        # 4. Create Result
        result = TestResult(
            run_id=str(uuid.uuid4()),
            test_id=spec.test_id,
            test_version=spec.test_version,
            ai_response=ai_response,
            evaluation=evaluation,
            metadata=metadata,
            timestamp=time.time()
        )
        
        return result

    def print_report(self, result: TestResult):
        print("\n" + "="*50)
        print(f"TEST REPORT: {result.test_id} (Run ID: {result.run_id})")
        print("="*50)
        
        # Reproducibility Snapshot
        print(f"Test Version:      {result.test_version}")
        print(f"System Version:    {result.metadata.system_version}")
        print(f"Git Commit:        {result.metadata.git_commit}")
        print(f"Git Dirty:         {str(result.metadata.git_dirty).lower()}")
        print(f"Provider:          {result.metadata.provider}")
        print(f"Model:             {result.metadata.model}")
        print(f"Model Version:     {result.metadata.model_version}")
        print(f"Prompt Hash:       {result.metadata.system_prompt_hash}")
        print(f"Config Hash:       {result.metadata.configuration_hash}")
        print(f"Evaluator Version: {result.metadata.evaluation_engine_version}")
        print(f"Timestamp:         {result.timestamp}")
        print("-" * 50)
        
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
