import json
import time
import uuid
from .schema import TestSpec, TestResult, ExecutionMetadata, EvaluationResult, EvaluationFailure, SessionResult, TurnResult, TurnSpec
from .metadata import get_git_info, hash_string, hash_dict
from .evaluator import Evaluator
from models.provider import BaseProvider, ProviderError, ProviderErrorType, UsageMetrics
from core.taxonomy import FailureTag, RootCause, Severity
from core.pricing import UsageRecord, PricingEngine
import dataclasses

class TestRunner:
    def __init__(self, provider: BaseProvider, evaluator: Evaluator):
        self.provider = provider
        self.evaluator = evaluator

    def run_test(self, spec: TestSpec) -> TestResult:
        print(f"Running Test: {spec.test_id}...")
        
        # 1. Send scenario to AI
        print(" -> Generating AI response...")
        provider_status = "SUCCESS"
        
        try:
            provider_response = self.provider.generate_response(spec.scenario)
            ai_response_text = provider_response.content
            
            # 2. Evaluate response
            print(" -> Evaluating response...")
            evaluation = self.evaluator.evaluate(spec, ai_response_text)
            
        except ProviderError as e:
            provider_status = e.error_type.value
            print(f" -> Provider Error: {provider_status}")
            ai_response_text = f"[{provider_status}] {e.message}"
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
        
        usage_records = []
        if provider_response and provider_response.usage:
            gen_usage = UsageRecord.from_response(
                role="generation",
                provider=provider_response.provider,
                model=provider_response.model,
                usage=provider_response.usage
            )
            usage_records.append(dataclasses.asdict(gen_usage))
        
        for layer in evaluation.layer_evaluations:
            if layer.layer_name == "llm_judge" and layer.metadata:
                judge_provider = layer.metadata.get("judge_provider", "unknown")
                judge_model = layer.metadata.get("judge_model", "unknown")
                # We could hash the prompt here or track prompt version
                judge_prompt_hash = hash_string(layer.metadata.get("prompt_template", "unknown"))
                
                judge_usage_dict = layer.metadata.get("usage")
                if judge_usage_dict:
                    judge_usage = UsageRecord.from_response(
                        role="judge",
                        provider=judge_provider,
                        model=judge_model,
                        usage=UsageMetrics(**judge_usage_dict)
                    )
                    usage_records.append(dataclasses.asdict(judge_usage))
        
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
            timestamp=time.time(),
            usage_json={"records": usage_records},
            provider_status=provider_status,
            attempt_number=1
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

    def run_session(self, spec: TestSpec) -> SessionResult:
        print(f"Running Stateful Session: {spec.test_id}...")
        
        session_id = str(uuid.uuid4())
        turns = []
        history = []
        
        # Initial scenario prompt goes as first message for context, but usually multi-turn tests
        # might just use turns directly. Let's send the scenario as a system/user context first.
        # For simplicity, we just use the scenario as the first turn or just let history accumulate.
        if spec.scenario:
            history.append({"role": "user", "content": spec.scenario})
            # Generate an initial response to establish context? Or just treat turns as user inputs.
            # Usually, if there are turns, the first turn is the first message. If scenario is provided, we can prepend it.
            
        turn_number = 1
        for turn_spec in spec.turns:
            print(f" -> Turn {turn_number}: User Input...")
            user_input = turn_spec.user_input
            
            
            provider_status = "SUCCESS"
            # 1. Send input with history
            try:
                # Some providers like venice and gemini support history. Mock does too now.
                provider_response = self.provider.generate_response(user_input, history=history)
                ai_response_text = provider_response.content
                
                # Update history
                history.append({"role": "user", "content": user_input})
                history.append({"role": "model", "content": ai_response_text})
                
                # 2. Evaluate turn
                print(" -> Evaluating turn...")
                # We create a temporary TestSpec to evaluate this specific turn's criteria
                temp_spec = TestSpec(
                    test_id=spec.test_id,
                    scenario=spec.scenario,
                    criteria=turn_spec.criteria,
                    required_behaviors=[],
                    forbidden_behaviors=[],
                    evaluation_criteria=[]
                )
                evaluation = self.evaluator.evaluate(temp_spec, ai_response_text)
                
            except ProviderError as e:
                provider_status = e.error_type.value
                print(f" -> Provider Error: {provider_status}")
                ai_response_text = f"[{provider_status}] {e.message}"
                provider_response = None
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
            
            turn_usage_records = []
            if provider_response and provider_response.usage:
                gen_usage = UsageRecord.from_response(
                    role="generation",
                    provider=provider_response.provider,
                    model=provider_response.model,
                    usage=provider_response.usage
                )
                turn_usage_records.append(dataclasses.asdict(gen_usage))
            
            for layer in evaluation.layer_evaluations:
                if layer.layer_name == "llm_judge" and layer.metadata:
                    judge_provider = layer.metadata.get("judge_provider", "unknown")
                    judge_model = layer.metadata.get("judge_model", "unknown")
                    judge_usage_dict = layer.metadata.get("usage")
                    if judge_usage_dict:
                        judge_usage = UsageRecord.from_response(
                            role="judge",
                            provider=judge_provider,
                            model=judge_model,
                            usage=UsageMetrics(**judge_usage_dict)
                        )
                        turn_usage_records.append(dataclasses.asdict(judge_usage))
                        
            turns.append(TurnResult(
                turn_id=str(uuid.uuid4()),
                turn_number=turn_number,
                user_input=user_input,
                ai_response=ai_response_text,
                evaluation=evaluation,
                timestamp=time.time(),
                usage_json={"records": turn_usage_records},
                provider_status=provider_status,
                attempt_number=1
            ))
            turn_number += 1
            
        # Session Evaluation
        final_evaluation = self.evaluator.evaluate_session(spec, turns)
        
        # Build Metadata
        git_commit, git_dirty = get_git_info()
        judge_provider, judge_model, judge_prompt_hash = "unknown", "unknown", "unknown"
        
        # Look for judge metadata from any turn
        for t in turns:
            for layer in t.evaluation.layer_evaluations:
                if layer.layer_name == "llm_judge" and layer.metadata:
                    judge_provider = layer.metadata.get("judge_provider", "unknown")
                    judge_model = layer.metadata.get("judge_model", "unknown")
                    judge_prompt_hash = hash_string(layer.metadata.get("prompt_template", "unknown"))
                    break
                    
        metadata = ExecutionMetadata(
            git_commit=git_commit,
            git_dirty=git_dirty,
            system_prompt_hash=hash_string(spec.scenario),
            configuration_hash=hash_dict(self.provider.config.as_dict()),
            provider=self.provider.config.provider_name,
            model=self.provider.config.model_name,
            model_version="unknown",
            judge_provider=judge_provider,
            judge_model=judge_model,
            judge_prompt_hash=judge_prompt_hash
        )
        
        session_usage_records = []
        # Pull usage from session level judge if any
        if final_evaluation.trajectory:
            session_judge_usage_dict = final_evaluation.session_metadata.get("usage")
            if session_judge_usage_dict:
                judge_usage = UsageRecord.from_response(
                    role="judge",
                    provider=final_evaluation.session_metadata.get("judge_provider", "unknown"),
                    model=final_evaluation.session_metadata.get("judge_model", "unknown"),
                    usage=UsageMetrics(**session_judge_usage_dict)
                )
                session_usage_records.append(dataclasses.asdict(judge_usage))
            
        return SessionResult(
            session_id=session_id,
            test_id=spec.test_id,
            test_version=spec.test_version,
            turns=turns,
            final_evaluation=final_evaluation,
            metadata=metadata,
            timestamp=time.time(),
            usage_json={"records": session_usage_records},
            provider_status="SUCCESS",
            attempt_number=1
        )

    def print_session_report(self, session: SessionResult):
        print("\n" + "="*60)
        print(f"STATEFUL SESSION REPORT: {session.test_id} (Session ID: {session.session_id})")
        print("="*60)
        
        for turn in session.turns:
            print(f"\n--- Turn {turn.turn_number} ---")
            print(f"User: {turn.user_input}")
            print(f"AI:   {turn.ai_response}")
            print(f"Turn Verdict: {'PASS' if turn.evaluation.passed else 'FAIL'}")
            if turn.evaluation.failures:
                for f in turn.evaluation.failures:
                    print(f"  -> Failure [{f.severity}]: {', '.join(f.tags)}")
                    print(f"     Observed: {f.observed_behavior}")
                    
        print("\n" + "-"*60)
        print(f"Final Session Verdict: {'PASS' if session.final_evaluation.passed else 'FAIL'}")
        print(f"Session Score:         {session.final_evaluation.score}")
        if session.final_evaluation.trajectory:
            print(f"Session Trajectory:    {session.final_evaluation.trajectory}")
        if session.final_evaluation.evidence_timeline:
            print("\nEvidence Timeline:")
            for ev in session.final_evaluation.evidence_timeline:
                print(f"  - {ev}")
        if session.final_evaluation.reasoning:
            print(f"\nReasoning: {session.final_evaluation.reasoning}")
        print("="*60 + "\n")
