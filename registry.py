import argparse
import json
import uuid
import datetime
from core.schema import ExperimentDefinition, DecisionPolicy
from core.experiment_registry import ExperimentRegistry, DecisionEngine
from core.statistics import ExperimentAnalytics

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Experiment Registry")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a new experiment")
    init_parser.add_argument("hypothesis", help="Experimental hypothesis")
    init_parser.add_argument("--baseline", required=True, help="Baseline run name")
    init_parser.add_argument("--candidate", required=True, help="Candidate run name")
    init_parser.add_argument("--budget", type=float, default=10.0)
    init_parser.add_argument("--max-cost-inc", type=float, default=20.0, help="Max cost increase %")
    init_parser.add_argument("--max-lat-inc", type=float, default=10.0, help="Max latency increase %")

    list_parser = subparsers.add_parser("list", help="List experiments")

    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a completed experiment")
    eval_parser.add_argument("experiment_id", help="Experiment ID to evaluate")

    args = parser.parse_args()
    reg = ExperimentRegistry()

    if args.command == "init":
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        pol = DecisionPolicy(max_cost_increase_pct=args.max_cost_inc, max_latency_increase_pct=args.max_lat_inc)
        exp = ExperimentDefinition(
            experiment_id=exp_id,
            hypothesis=args.hypothesis,
            baseline=args.baseline,
            candidate=args.candidate,
            budget=args.budget,
            decision_policy=pol
        )
        reg.create(exp)
        print(f"Created Experiment: {exp_id}")
        print(f"Hypothesis: {exp.hypothesis}")

    elif args.command == "list":
        exps = reg.list_all()
        if not exps:
            print("No experiments found.")
            return

        print(f"{'ID':<15} | {'STATUS':<10} | {'DECISION':<12} | {'HYPOTHESIS'}")
        print("-" * 60)
        for exp in exps:
            dec = exp.final_decision.value if exp.final_decision else "N/A"
            print(f"{exp.experiment_id:<15} | {exp.status:<10} | {dec:<12} | {exp.hypothesis}")

    elif args.command == "evaluate":
        exp = reg.get(args.experiment_id)
        if not exp:
            print(f"Error: Experiment {args.experiment_id} not found.")
            return



        from statistics import load_baseline
        b_runs = load_baseline(exp.baseline)
        c_runs = load_baseline(exp.candidate)

        if not b_runs or not c_runs:
            print(f"Error: Missing runs for baseline '{exp.baseline}' or candidate '{exp.candidate}'")
            exp = reg.update_status(exp.experiment_id, "FAILED")
            return

        analytics = ExperimentAnalytics(b_runs, c_runs)
        stats = {
            "score_res": analytics.analyze_scores(),
            "crit_res": analytics.analyze_criticals(),
            "res_res": analytics.analyze_resources(),
            "tag_res": analytics.analyze_tags()
        }

        engine = DecisionEngine(exp.decision_policy)
        decision = engine.evaluate(stats)

        exp = reg.update_status(exp.experiment_id, "COMPLETED", decision, json.dumps(stats))

        print(f"Experiment {exp.experiment_id} Evaluated.")
        print(f"Hypothesis: {exp.hypothesis}")
        print(f"Decision:   {decision.value}")

        cost_delta = stats['res_res']['cost']['delta_pct']
        lat_delta = stats['res_res']['latency']['delta_pct']
        score_delta = stats['score_res']['delta']
        sig = stats['score_res']['significant']

        print(f"\nStats:")
        print(f"- Score Change: {score_delta:+.2f} (Significant: {sig})")
        print(f"- Cost Change:  {cost_delta:+.1f}%")
        print(f"- Lat Change:   {lat_delta:+.1f}%")
        print(f"- Crit Safety:  {'REGRESSION' if stats['crit_res']['regression'] else 'STABLE/IMPROVED'}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
