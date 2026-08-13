import os
import sys
import json
import argparse

from core.schema import TestSpec
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import ProviderConfig
from models.factory import get_provider
from database.sqlite import save_test_result

def load_test_spec(filepath: str) -> TestSpec:
    with open(filepath, 'r') as f:
        data = json.load(f)
    return TestSpec(**data)

def main():
    parser = argparse.ArgumentParser(description="Run Behave Evaluator")
    parser.add_argument("test_file", help="Path to the test JSON file")
    parser.add_argument("--provider", default="mock", choices=["mock", "gemini", "venice"], help="Provider to use")
    parser.add_argument("--model", default="unknown", help="Model name (e.g. gemini-1.5-flash)")
    parser.add_argument("--api-key", default=None, help="API key for the provider (can also use env vars)")
    
    args = parser.parse_args()

    test_file = args.test_file
    if not os.path.exists(test_file):
        print(f"Error: Test file '{test_file}' not found.")
        sys.exit(1)

    spec = load_test_spec(test_file)

    # We provide a mock AI model that exhibits the exact failure mode we want to catch.
    # It assumes the sensor is bad and recommends replacement immediately.
    mock_responses = {
        "P0720": "Those codes indicate a problem with the Output Speed Sensor circuit. You should replace the sensor to fix the issue.",
        "$500": "Buy a professional diagnostic scanner for $500. You will make your money back in 5 jobs."
    }
    
    api_key = args.api_key
    if args.provider == "gemini" and not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    elif args.provider == "venice" and not api_key:
        api_key = os.environ.get("VENICE_API_KEY")
        
    config = ProviderConfig(
        provider_name=args.provider, 
        model_name=args.model,
        api_key=api_key
    )
    provider = get_provider(config, mock_responses=mock_responses)
    
    evaluator = Evaluator()
    runner = TestRunner(provider=provider, evaluator=evaluator)
    
    result = runner.run_test(spec)
    
    # Phase 1: Persist the result
    save_test_result(result)
    
    runner.print_report(result)

if __name__ == "__main__":
    main()
