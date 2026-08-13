import sys
import argparse
from core.baseline import create_baseline

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Baseline Management")
    subparsers = parser.add_subparsers(dest="command")
    
    create_parser = subparsers.add_parser("create", help="Create a frozen baseline")
    create_parser.add_argument("name", help="Name of the baseline")
    create_parser.add_argument("--provider", default=None, help="Optional provider to filter by")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_baseline(args.name, args.provider)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
