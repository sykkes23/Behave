import os
import sys
import argparse

from core.schema import TestSpec
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import ProviderConfig
from models.factory import get_provider
from database.sqlite import save_test_result, save_session_result
import json

from core.schema import TestSpec, TurnSpec, EvaluationCriterion

def load_test_spec(filepath: str) -> TestSpec:
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    turns = []
    for t in data.get("turns", []):
        criteria = [EvaluationCriterion(**c) for c in t.get("criteria", [])]
        turns.append(TurnSpec(
            user_input=t.get("user"),
            criteria=criteria,
            expected_behavior=t.get("expected_behavior", "")
        ))
    data["turns"] = turns
    
    if "criteria" in data:
        data["criteria"] = [EvaluationCriterion(**c) for c in data["criteria"]]
        
    return TestSpec(**data)

def main():
    parser = argparse.ArgumentParser(description="Run Behave Evaluator Multi-Provider Experiment")
    parser.add_argument("target", help="Path to the test JSON file or a corpus directory")
    parser.add_argument("--providers", default="mock", help="Comma-separated list of providers to test (e.g., mock,gemini,venice)")
    parser.add_argument("--max-cost", type=float, help="Maximum budget in USD for this experiment.")
    parser.add_argument("--strategy", default="FULL", help="Selection strategy (FULL, RANDOM, BALANCED, etc.)")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of tests to select")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for selection")
    
    args = parser.parse_args()

    target_path = args.target
    if not os.path.exists(target_path):
        print(f"Error: Target '{target_path}' not found.")
        sys.exit(1)
        
    specs = []
    if os.path.isdir(target_path):
        from core.corpus import CorpusManager
        from core.selector import TestSelector, SelectionStrategy
        
        manager = CorpusManager(target_path)
        selector = TestSelector(corpus_dir=target_path)
        
        try:
            strategy = SelectionStrategy[args.strategy.upper()]
        except KeyError:
            print(f"Error: Unknown strategy '{args.strategy}'.")
            sys.exit(1)
            
        manifest = selector.select(
            strategy=strategy,
            limit=args.limit,
            provider=providers_list[0],  # Use first provider for historical context
            seed=args.seed,
            max_cost=args.max_cost
        )
        
        selected_ids = {st.test_id for st in manifest.selected_tests}
        specs = [manager.tests[tid] for tid in selected_ids if tid in manager.tests]
        
        print(f"Adaptive Selector applied '{strategy.value}': Selected {len(specs)} tests out of {len(manager.get_valid_tests())} valid tests.")
        
        # Save selection manifest
        import dataclasses
        import json
        manifest_dir = "experiments"
        if not os.path.exists(manifest_dir): os.makedirs(manifest_dir)
        exp_dir = os.path.join(manifest_dir, manifest.experiment_id)
        os.makedirs(exp_dir)
        with open(os.path.join(exp_dir, "selection.json"), "w") as f:
            json.dump(dataclasses.asdict(manifest), f, indent=2)
            
    else:
        specs = [load_test_spec(target_path)]
    providers_list = [p.strip() for p in args.providers.split(',')]
    
    print(f"Starting experiment for test: {spec.test_id}")
    print(f"Target providers: {', '.join(providers_list)}\n")
    
    evaluator = Evaluator()
    
    experiment_results = []
    total_cost_accumulated = 0.0
    budget_exceeded = False
    
    for provider_name in providers_list:
        if budget_exceeded: break
        
        print(f"\n{'#' * 60}")
        print(f"### EXECUTING PROVIDER: {provider_name.upper()}")
        print(f"{'#' * 60}")
        
        # Pull API keys from environment
        api_key = None
        if provider_name == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
        elif provider_name == "venice":
            api_key = os.environ.get("VENICE_API_KEY")
            
        config = ProviderConfig(
            provider_name=provider_name,
            model_name="unknown",
            api_key=api_key
        )
        
        try:
            # We inject the mock responses just in case the mock provider is selected
            mock_responses = {
                "P0720": "Those codes indicate a problem with the Output Speed Sensor circuit. You should replace the sensor to fix the issue.",
                "$500": "Buy a professional diagnostic scanner for $500. You will make your money back in 5 jobs."
            }
            
            provider = get_provider(config, mock_responses=mock_responses)
            runner = TestRunner(provider=provider, evaluator=evaluator)
            
            for spec in specs:
                if args.max_cost is not None and total_cost_accumulated >= args.max_cost:
                    print(f"\nSTOP: BUDGET_EXCEEDED (Accumulated: ${total_cost_accumulated:.4f} / Budget: ${args.max_cost:.4f})")
                    budget_exceeded = True
                    break
                    
                print(f"\nRunning target: {spec.test_id} ...")
                
                if spec.turns:
                    result = runner.run_session(spec)
                    save_session_result(result)
                else:
                    result = runner.run_test(spec)
                    save_test_result(result)
                    
                experiment_results.append({
                    "provider": provider_name,
                    "result": result
                })
                
                # Accumulate cost
                usage_records = result.usage_json.get("records", [])
                for rec in usage_records:
                    if rec.get("cost_usd") is not None:
                        total_cost_accumulated += rec["cost_usd"]
            
        except Exception as e:
            print(f"FATAL ERROR while testing provider {provider_name}: {str(e)}")

    print("\n" + "="*50)
    print("EXPERIMENT SUMMARY")
    print("="*50)
    print(f"Target: {target_path}")
    
    for entry in experiment_results:
        res = entry["result"]
        prov = entry["provider"]
        model = res.metadata.model
        is_session = hasattr(res, 'turns')
        
        eval_result = res.final_evaluation if is_session else res.evaluation
        
        score = eval_result.score
        passed = eval_result.passed
        critical_fails = eval_result.critical_failure_count
        
        gen_cost = 0.0
        judge_cost = 0.0
        tot_tok = 0
        in_tok = 0
        out_tok = 0
        reqs = 0
        reqs_succ = 0
        reqs_err = 0
        
        records = res.usage_json.get("records", [])
        for rec in records:
            if rec.get("role") == "generation":
                gen_cost += rec.get("cost_usd") or 0.0
                tot_tok += rec.get("usage", {}).get("total_tokens") or 0
                in_tok += rec.get("usage", {}).get("input_tokens") or 0
                out_tok += rec.get("usage", {}).get("output_tokens") or 0
            elif rec.get("role") == "judge":
                judge_cost += rec.get("cost_usd") or 0.0
                
        tot_cost = gen_cost + judge_cost
        
        if is_session:
            reqs = len(res.turns)
            reqs_succ = sum(1 for t in res.turns if t.provider_status == "SUCCESS")
            reqs_err = reqs - reqs_succ
        else:
            reqs = 1
            reqs_succ = 1 if res.provider_status == "SUCCESS" else 0
            reqs_err = 1 - reqs_succ
            
        print("\nProvider: " + prov)
        print("Model: " + model)
        print("\nRESULT")
        print("------")
        print(f"Behavioral Score:       {score}")
        print(f"Final Verdict:          {'PASS' if passed else 'FAIL'}")
        print(f"Critical Failures:      {critical_fails}")
        print("\nUSAGE")
        print("-----")
        print(f"Input Tokens:           {in_tok}")
        print(f"Output Tokens:          {out_tok}")
        print(f"Total Tokens:           {tot_tok}")
        print("\nCOST")
        print("----")
        print(f"Generation:             ${gen_cost:.4f}")
        print(f"Judge:                  ${judge_cost:.4f}")
        print(f"Total:                  ${tot_cost:.4f}")
        print("\nRELIABILITY")
        print("-----------")
        print(f"Requests:               {reqs}")
        print(f"Successful:             {reqs_succ}")
        print(f"Errors:                 {reqs_err}")
        print(f"Retries:                0")
        
    print("\nPOLICY")
    print("------")
    if experiment_results:
        meta = experiment_results[0]["result"].metadata
        print(f"Scoring Policy:         {meta.scoring_policy_version}")
        print(f"Critical Policy:        {meta.critical_policy_version}")
        print(f"Pricing Version:        {meta.pricing_version}")
    print("="*50)

if __name__ == "__main__":
    main()
