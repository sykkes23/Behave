import os
import sys
import argparse
import json

# Add parent directory to path so we can import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.schema import TestSpec, EvaluationCriterion, LayerVerdict
from models.provider import ProviderConfig
from models.factory import get_provider
from core.judge import LLMJudge

def load_calibration_data(filepath: str) -> list:
    with open(filepath, 'r') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Calibrate LLM Judge")
    parser.add_argument("calibration_file", help="Path to calibration json file", nargs='?', default="data/calibration.json")
    parser.add_argument("--provider", default="mock", help="Judge provider (mock, gemini, venice)")
    parser.add_argument("--api-key", default=None, help="API key")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.calibration_file):
        print(f"Error: {args.calibration_file} not found.")
        sys.exit(1)
        
    api_key = args.api_key
    if args.provider == "gemini" and not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    elif args.provider == "venice" and not api_key:
        api_key = os.environ.get("VENICE_API_KEY")
        
    config = ProviderConfig(provider_name=args.provider, api_key=api_key)
    
    # Mock some responses just for the mock judge
    mock_responses = {
        "assume": json.dumps({"verdict": "FAIL", "reasoning": "Assumed profitability", "criteria_results": [{"criterion_id": "no_assumptions", "verdict": "FAIL", "evidence": "money back in 5 jobs"}], "failures": [{"tags": ["unsupported_assumption"]}]}),
        "test": json.dumps({"verdict": "PASS", "reasoning": "Tested circuit", "criteria_results": [{"criterion_id": "diagnostic_steps", "verdict": "PASS", "evidence": "multimeter"}], "failures": []}),
        "details": json.dumps({"verdict": "PASS", "reasoning": "Asked for details", "criteria_results": [{"criterion_id": "ask_clarifying", "verdict": "PASS", "evidence": "needs more details"}], "failures": []}),
        "ignore previous": json.dumps({"verdict": "FAIL", "reasoning": "Injection attempt", "criteria_results": [{"criterion_id": "no_guess", "verdict": "FAIL", "evidence": "ignore previous"}], "failures": [{"tags": ["instruction_failure"]}]})
    }
    
    provider = get_provider(config, mock_responses=mock_responses)
    judge = LLMJudge(provider=provider)
    
    cases = load_calibration_data(args.calibration_file)
    
    total_cases = len(cases)
    pass_agreement = 0
    fail_agreement = 0
    uncertain_agreement = 0
    disagreements = 0
    malformed = 0
    
    print(f"Starting judge calibration against {total_cases} cases using provider '{args.provider}'.\n")
    
    for case in cases:
        spec = TestSpec(
            test_id=case["id"],
            scenario=case["scenario"],
            criteria=[EvaluationCriterion(id=c["id"], description=c["description"]) for c in case["criteria"]]
        )
        
        layer_verdict, reasoning, failures, criteria_results, metadata_info = judge.evaluate(spec, case["response"])
        
        expected_verdict = case["human_verdict"]
        judge_verdict = layer_verdict.value
        
        print(f"Case {case['id']}: Human={expected_verdict}, Judge={judge_verdict}")
        
        if layer_verdict == LayerVerdict.ERROR:
            malformed += 1
            disagreements += 1
        elif judge_verdict == expected_verdict:
            if expected_verdict == "PASS": pass_agreement += 1
            if expected_verdict == "FAIL": fail_agreement += 1
            if expected_verdict == "UNCERTAIN": uncertain_agreement += 1
        else:
            disagreements += 1
            print(f"  -> DISAGREEMENT: Human reasoning: '{case['human_rationale']}'. Judge reasoning: '{reasoning}'")
            
    print("\nCalibration Results:")
    print("-" * 20)
    print(f"Total Cases:         {total_cases}")
    print(f"PASS Agreement:      {pass_agreement}")
    print(f"FAIL Agreement:      {fail_agreement}")
    print(f"UNCERTAIN Agreement: {uncertain_agreement}")
    print(f"Disagreements:       {disagreements}")
    print(f"Malformed Outputs:   {malformed}")
    
if __name__ == "__main__":
    main()
