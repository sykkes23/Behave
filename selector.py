import argparse
import json
import dataclasses
from core.selector import TestSelector, SelectionStrategy

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Adaptive Test Selector")
    subparsers = parser.add_subparsers(dest="command")
    
    preview_parser = subparsers.add_parser("preview", help="Preview test selection")
    preview_parser.add_argument("dir", help="Corpus directory")
    preview_parser.add_argument("--strategy", default="BALANCED", help="Selection strategy")
    preview_parser.add_argument("--limit", type=int, default=10, help="Maximum tests to select")
    preview_parser.add_argument("--provider", default=None, help="Provider for historical context")
    preview_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    preview_parser.add_argument("--max-cost", type=float, default=None, help="Budget limit in USD")
    
    explain_parser = subparsers.add_parser("explain", help="Explain why a test would be selected")
    explain_parser.add_argument("test_id", help="The test ID to explain")
    explain_parser.add_argument("--dir", default="tests", help="Corpus directory")
    
    args = parser.parse_args()
    
    if args.command == "preview":
        strategy = SelectionStrategy[args.strategy.upper()]
        selector = TestSelector(corpus_dir=args.dir)
        manifest = selector.select(
            strategy=strategy,
            limit=args.limit,
            provider=args.provider,
            seed=args.seed,
            max_cost=args.max_cost
        )
        
        print("\n" + "="*50)
        print("SELECTION MANIFEST PREVIEW")
        print("="*50)
        print(f"Strategy: {manifest.strategy}")
        print(f"Seed: {manifest.seed}")
        print(f"Target limit: {args.limit}")
        print(f"Selected tests: {len(manifest.selected_tests)}")
        print(f"Unselected tests: {manifest.unselected_tests}")
        
        print("\n--- Selected Tests ---")
        for st in manifest.selected_tests:
            print(f"\n{st.test_id} (Priority Score: {st.priority_score})")
            print("Reasons:")
            for r in st.reasons:
                print(f"  - {r}")
                
        if manifest.coverage_warnings:
            print("\n--- Coverage Warnings ---")
            for w in manifest.coverage_warnings:
                print(f"WARNING: {w}")
                
    elif args.command == "explain":
        selector = TestSelector(corpus_dir=args.dir)
        manifest = selector.select(SelectionStrategy.BALANCED, limit=1000)
        
        found = False
        for st in manifest.selected_tests:
            if st.test_id == args.test_id:
                found = True
                print(f"Explanation for: {st.test_id}")
                print(f"Priority Score: {st.priority_score}")
                print("Reasons:")
                for r in st.reasons:
                    print(f"  - {r}")
                break
                
        if not found:
            print(f"Test {args.test_id} not found in valid corpus.")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
