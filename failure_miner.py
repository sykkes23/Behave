import argparse
from core.miner import FailureMiner
import json

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Failure Miner")
    subparsers = parser.add_subparsers(dest="command")
    
    analyze_parser = subparsers.add_parser("analyze", help="Analyze database for failure patterns")
    
    gen_parser = subparsers.add_parser("generate", help="Generate variants based on a failure tag")
    gen_parser.add_argument("--failure", required=True, help="The failure tag to mine (e.g. unsupported_assumption)")
    gen_parser.add_argument("--count", type=int, default=1, help="Number of variants to generate")
    
    args = parser.parse_args()
    miner = FailureMiner()
    
    if args.command == "analyze":
        stats = miner.analyze_failures()
        print("="*50)
        print("FAILURE ANALYSIS")
        print("="*50)
        print("\n--- By Tag ---")
        for k, v in sorted(stats.get("tags", {}).items(), key=lambda x: x[1], reverse=True):
            print(f"{k.ljust(30)} {v}")
            
        print("\n--- Affected Tests (Top 5) ---")
        for tag, tests in list(stats.get("affected_tests", {}).items())[:5]:
            print(f"{tag}: {', '.join(tests[:3])}{'...' if len(tests) > 3 else ''}")
            
    elif args.command == "generate":
        variants = miner.generate_variant(args.failure, args.count)
        if not variants:
            print("No variants generated.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
