import json
import time
import uuid
from .schema import TestSpec, TestResult, ExecutionMetadata, EvaluationResult, EvaluationFailure
from .metadata import get_git_info, hash_string, hash_dict
from .evaluator import Evaluator
from models.provider import BaseProvider, ProviderError
from core.taxonomy import FailureTag, RootCause, Severity

class TestRunner:
    def __init__(self, provider: BaseProvider, evaluator: Evaluator):
        self.provider = provider
        self.evaluator = evaluator

    def run_test(self, spec: TestSpec) -> TestResult:
        print(f"Running Test: {spec.test_id}...")
        
        # 1. Send scenario to AI
        print(" -> Generating AI response...")
        try:
            provider_response = self.provider.generate_response(spec.scenario)
            ai_response_text = provider_response.content
            
            # 2. Evaluate response
            print(" -> Evaluating response...")
            evaluation = self.evaluator.evaluate(spec, ai_response_text)
            
        except ProviderError as e:
            print(f" -> Provider Error: {e.error_type.value}")
            ai_response_text = f"[{e.error_type.value}] {e.message}"
            provider_response = None
            
            # Create a synthetic evaluation failure so it doesn't get lost,
            # but mark it distinctly as an infrastructure error, not an AI behavioral failure.
            evaluation = EvaluationResult(
                passed=False,
                score=0.0,
                failures=[EvaluationFailure(
                    tags=[e.error_type.value],
                    root_cause=RootCause.UNKNOWN.value,
                    observed_behavior=e.message,
                    expected_behavior="Valid API response",
                    severity=Severity.CRITICAL.value
                )],
                reasoning="Test aborted due to provider error."
            )
        
        # 3. Build Metadata
        git_commit, git_dirty = get_git_info()
        
        judge_provider = "unknown"
        judge_model = "unknown"
        judge_prompt_hash = "unknown"
        
        for layer in evaluation.layer_evaluations:
            if layer.layer_name == "llm_judge" and layer.metadata:
                judge_provider = layer.metadata.get("judge_provider", "unknown")
                judge_model = layer.metadata.get("judge_model", "unknown")
                # We could hash the prompt here or track prompt version
                judge_prompt_hash = hash_string(layer.metadata.get("prompt_template", "unknown"))
        
        metadata = ExecutionMetadata(
            git_commit=git_commit,
            git_dirty=git_dirty,
            system_prompt_hash=hash_string("You are a helpful automotive assistant."), # Mock system prompt
            configuration_hash=hash_dict(self.provider.config.as_dict()),
            provider=provider_response.provider if provider_response else self.provider.config.provider_name,
            model=provider_response.model if provider_response else self.provider.config.model_name,
            model_version=provider_response.model_version if provider_response else "unknown",
            judge_provider=judge_provider,
            judge_model=judge_model,
            judge_prompt_hash=judge_prompt_hash
        )
        
        # 4. Create Result
        result = TestResult(
            run_id=str(uuid.uuid4()),
            test_id=spec.test_id,
            test_version=spec.test_version,
            ai_response=ai_response_text,
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
        print(f"Judge Provider:    {result.metadata.judge_provider}")
        print(f"Judge Model:       {result.metadata.judge_model}")
        print(f"Prompt Hash:       {result.metadata.system_prompt_hash}")
        print(f"Config Hash:       {result.metadata.configuration_hash}")
        print(f"Evaluator Version: {result.metadata.evaluation_engine_version}")
        print(f"Timestamp:         {result.timestamp}")
        print("-" * 50)
        
        print(f"Automatic Verdict: {'PASS' if result.evaluation.passed else 'FAIL'}")
        print(f"Score:             {result.evaluation.score}")
        
        # Display Layer Verdicts to show disagreement if any
        if hasattr(result.evaluation, 'layer_evaluations') and result.evaluation.layer_evaluations:
            print("\nLayer Verdicts:")
            for layer in result.evaluation.layer_evaluations:
                print(f"  - {layer.layer_name.capitalize():<15}: {layer.verdict.value}")
        
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
