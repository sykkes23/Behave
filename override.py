import sys
import time
from database.sqlite import update_human_override, get_test_result

def main():
    if len(sys.argv) < 4:
        print("Usage: python override.py <run_id> <verdict> <reason>")
        print("Verdicts: PASS, FAIL, PARTIAL, INVALID_TEST")
        sys.exit(1)

    run_id = sys.argv[1]
    verdict = sys.argv[2].upper()
    reason = " ".join(sys.argv[3:])
    
    valid_verdicts = ["PASS", "FAIL", "PARTIAL", "INVALID_TEST"]
    if verdict not in valid_verdicts:
        print(f"Error: Verdict must be one of {valid_verdicts}")
        sys.exit(1)

    result = get_test_result(run_id)
    if not result:
        print(f"Error: Test run ID '{run_id}' not found.")
        sys.exit(1)

    print(f"\n--- Current Test Run ({run_id}) ---")
    print(f"Test ID: {result.test_id}")
    print(f"Automatic Verdict: {'PASS' if result.evaluation.passed else 'FAIL'}")
    if result.evaluation.human_verdict:
        print(f"Existing Human Verdict: {result.evaluation.human_verdict}")
        print(f"Existing Human Reason: {result.evaluation.human_reason}")

    print(f"\nApplying Override...")
    print(f"New Verdict: {verdict}")
    print(f"Reason: {reason}")
    
    update_human_override(run_id, verdict, reason, time.time())
    print("Successfully applied human override.")

if __name__ == "__main__":
    main()
