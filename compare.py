import argparse
from core.compare import compare_baselines

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Baseline Comparison Engine")
    parser.add_argument("baseline", help="Name of the frozen baseline to use as control")
    parser.add_argument("candidate", help="Name of the frozen baseline to use as candidate")
    
    args = parser.parse_args()
    
    compare_baselines(args.baseline, args.candidate)

if __name__ == "__main__":
    main()
