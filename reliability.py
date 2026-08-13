import argparse
import json
from core.reliability import MeasurementIntegrity

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Measurement Reliability")
    subparsers = parser.add_subparsers(dest="command")
    
    summary_parser = subparsers.add_parser("summary", help="Print reliability dashboard")
    
    calibrate_parser = subparsers.add_parser("calibrate", help="Run calibration regression gate")
    calibrate_parser.add_argument("--provider", default="mock", help="Judge provider to calibrate")
    calibrate_parser.add_argument("--model", default="mock", help="Judge model to calibrate")
    
    args = parser.parse_args()
    
    mi = MeasurementIntegrity()
    
    if args.command == "summary":
        report = mi.generate_report()
        if not report:
            print("No data available.")
            return
            
        print("Measurement Integrity")
        print("────────────────────────────────")
        print(f"Evaluations:             {report['total_evaluations']}")
        print(f"Reliable:                  {report['status_counts']['RELIABLE']}")
        print(f"Questionable:              {report['status_counts']['QUESTIONABLE']}")
        print(f"Unreliable:                 {report['status_counts']['UNRELIABLE']}")
        print(f"Insufficient data:          {report['status_counts']['INSUFFICIENT_DATA']}")
        
        hr = report['human_override_stats']
        print(f"\nHuman Override Rate:      {hr['override_rate']*100:.1f}% ({hr['total_overridden']}/{hr['total_reviewed']})")
        
        print(f"\nPotential Test Ambiguity: {len(report['ambiguous_tests'])} tests")
        for at in report['ambiguous_tests']:
            print(f" - {at['test_id']} (Disagreement: {at['disagreement_rate']*100:.1f}%, Override: {at['override_rate']*100:.1f}%)")
            
        with open("reliability_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print("\nFull report saved to reliability_report.json")
            
    elif args.command == "calibrate":
        res = mi.calibrate(args.provider, args.model)
        print("Calibration Results")
        print("────────────────────────────")
        print(f"Cases:              {res['cases']}")
        print(f"Raw Agreement:      {res['raw_agreement']*100:.0f}%")
        print(f"Cohen's Kappa:      {res['cohens_kappa']}")
        print(f"Critical Recall:    {res['critical_recall']*100:.0f}%")
        print(f"Critical Precision: {res['critical_precision']*100:.0f}%")
        print(f"Malformed Outputs:  {res['malformed_outputs']}")
        print("\nPrevious:")
        print(f"Raw Agreement:      {res['previous_raw_agreement']*100:.0f}%")
        print(f"Cohen's Kappa:      {res['previous_cohens_kappa']}")
        print(f"\nStatus:\n{res['status']}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
