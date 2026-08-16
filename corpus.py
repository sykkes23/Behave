import argparse
from core.corpus import CorpusManager

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Corpus Management")
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze corpus coverage and status")
    analyze_parser.add_argument("--dir", default="tests", help="Directory containing the corpus (default: tests)")

    subparsers.add_parser("review", help="List all EXPERIMENTAL tests pending review")

    approve_parser = subparsers.add_parser("approve", help="Approve an EXPERIMENTAL test to VALID")
    approve_parser.add_argument("test_id", help="The test_id to approve")

    reject_parser = subparsers.add_parser("reject", help="Reject an EXPERIMENTAL test to INVALID")
    reject_parser.add_argument("test_id", help="The test_id to reject")

    args = parser.parse_args()

    if args.command == "analyze":
        manager = CorpusManager(corpus_dir=args.dir if hasattr(args, 'dir') else "tests")
        manager.print_coverage_report()
    elif args.command == "review":
        manager = CorpusManager(corpus_dir="tests")
        experimental = [t for t in manager.tests.values() if t.status.upper() == "EXPERIMENTAL"]
        print(f"Found {len(experimental)} tests pending review:\n")
        for t in experimental:
            print(f"- {t.test_id} (Parent: {t.parent_test}, Reason: {t.generation_reason})")
    elif args.command in ("approve", "reject"):
        manager = CorpusManager(corpus_dir="tests")
        if args.test_id not in manager.tests:
            print(f"Test {args.test_id} not found in corpus.")
            return

        import os, json, dataclasses
        spec = manager.tests[args.test_id]


        target_path = None
        for root, _, files in os.walk("tests"):
            for file in files:
                if file.endswith(".json"):
                    fp = os.path.join(root, file)
                    with open(fp, "r") as f:
                        d = json.load(f)
                        if d.get("test_id") == args.test_id:
                            target_path = fp
                            break
            if target_path: break

        if not target_path:
            print(f"Could not locate file for {args.test_id}")
            return

        spec.status = "VALID" if args.command == "approve" else "INVALID"

        with open(target_path, "w") as f:
            json.dump(dataclasses.asdict(spec), f, indent=2)

        print(f"Marked {args.test_id} as {spec.status} in {target_path}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
