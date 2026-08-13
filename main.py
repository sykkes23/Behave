import os
import sys
import json

from core.schema import TestSpec
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.mock import MockAIModel
from database.sqlite import save_test_result

def load_test_spec(filepath: str) -> TestSpec:
    with open(filepath, 'r') as f:
        data = json.load(f)
    return TestSpec(**data)

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_test.json>")
        sys.exit(1)

    test_file = sys.argv[1]
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
    
    ai_model = MockAIModel(predefined_responses=mock_responses)
    evaluator = Evaluator()
    runner = TestRunner(ai_model=ai_model, evaluator=evaluator)
    
    result = runner.run_test(spec)
    
    # Phase 1: Persist the result
    save_test_result(result)
    
    runner.print_report(result)

if __name__ == "__main__":
    main()
