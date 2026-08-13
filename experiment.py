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
    parser.add_argument("test_file", help="Path to the test JSON file")
    parser.add_argument("--providers", default="mock", help="Comma-separated list of providers to test (e.g., mock,gemini,venice)")
    
    args = parser.parse_args()

    test_file = args.test_file
    if not os.path.exists(test_file):
        print(f"Error: Test file '{test_file}' not found.")
        sys.exit(1)
        
    spec = load_test_spec(test_file)
    providers_list = [p.strip() for p in args.providers.split(',')]
    
    print(f"Starting experiment for test: {spec.test_id}")
    print(f"Target providers: {', '.join(providers_list)}\n")
    
    evaluator = Evaluator()
    
    for provider_name in providers_list:
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
            
            if spec.turns:
                result = runner.run_session(spec)
                save_session_result(result)
                runner.print_session_report(result)
            else:
                result = runner.run_test(spec)
                save_test_result(result)
                runner.print_report(result)
            
        except Exception as e:
            print(f"FATAL ERROR while testing provider {provider_name}: {str(e)}")

if __name__ == "__main__":
    main()
