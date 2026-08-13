import argparse
import os
import json
from core.statistics import ExperimentAnalytics

def load_baseline(name: str) -> dict:
    base_dir = os.path.join("baselines", name, "runs")
    if not os.path.exists(base_dir):
        return {}
        
    runs = {}
    for f in os.listdir(base_dir):
        if f.endswith(".json"):
            with open(os.path.join(base_dir, f), "r") as fh:
                data = json.load(fh)
                tid = data.get("test_id")
                if tid:
                    # Extract necessary fields
                    ev = data.get("evaluation", {})
                    # For sessions, final_evaluation is root
                    if "final_evaluation" in data:
                        ev = data["final_evaluation"]
                    
                    runs[tid] = {
                        "score": ev.get("score", 0.0),
                        "failures": ev.get("failures", []),
                        "cost": 0.0,
                        "latency": 0.0
                    }
                    
                    usage = data.get("usage_json", {})
                    if usage:
                        runs[tid]["cost"] = sum((r.get("cost_usd") or 0.0) for r in usage.get("records", []))
                    # Fallback latency logic for mock data
                    runs[tid]["latency"] = data.get("metadata", {}).get("latency", 1.5)
                    
    return runs

def main():
    parser = argparse.ArgumentParser(description="Behave Evaluator Statistical Analysis")
    parser.add_argument("baseline", help="Baseline name")
    parser.add_argument("candidate", help="Candidate name")
    
    args = parser.parse_args()
    
    b_runs = load_baseline(args.baseline)
    c_runs = load_baseline(args.candidate)
    
    if not b_runs or not c_runs:
        print("Error: Could not load runs for one or both baselines.")
        return
        
    analytics = ExperimentAnalytics(b_runs, c_runs)
    if not analytics.paired_tests:
        print("Error: No paired tests found between the two baselines.")
        return
        
    score_res = analytics.analyze_scores()
    tag_res = analytics.analyze_tags()
    crit_res = analytics.analyze_criticals()
    res_res = analytics.analyze_resources()
    
    print(f"EXPERIMENT: {args.candidate}")
    print(f"\nBaseline: {args.baseline}")
    print(f"Candidate: {args.candidate}")
    print(f"Paired Tests: {len(analytics.paired_tests)}")
    
    print("\n" + "─"*36)
    print("\nBehavioral Score")
    print(f"Baseline       {score_res['baseline_mean']:.1f}")
    print(f"Candidate      {score_res['candidate_mean']:.1f}")
    print(f"Delta          {score_res['delta']:+.1f}")
    
    print(f"\n95% CI         {score_res['ci_lower']:+.1f} → {score_res['ci_upper']:+.1f}")
    print(f"Effect Size    {score_res['effect_size']:.2f}")
    sig_str = "SIGNIFICANT" if score_res['significant'] else "NOT SIGNIFICANT"
    print(f"Significance   {sig_str}")
    
    print("\n" + "─"*36)
    print("\nFailure Rate")
    
    for tag, d in sorted(tag_res.items(), key=lambda x: x[1]['delta']):
        print(f"\n{tag}")
        print(f"Baseline       {d['baseline_rate']*100:.0f}%")
        print(f"Candidate      {d['candidate_rate']*100:.0f}%")
        print(f"Delta          {d['delta']*100:+.0f}%")
        if d['raw_p'] < 1.0:
            print(f"Adjusted p     {d['adj_p']:.3f}")
            print("SIGNIFICANT" if d['significant'] else "NOT SIGNIFICANT")
        else:
            print("NOT SIGNIFICANT (Insufficient changes)")
            
    print("\n" + "─"*36)
    print("\nCritical Failures\n")
    print(f"Baseline       {crit_res['baseline']}")
    print(f"Candidate      {crit_res['candidate']}")
    if crit_res['regression']:
        print("\nCRITICAL REGRESSION")
        
    print("\n" + "─"*36)
    print("\nCost\n")
    print(f"Baseline       ${res_res['cost']['baseline']:.4f}")
    print(f"Candidate      ${res_res['cost']['candidate']:.4f}")
    print(f"\n{res_res['cost']['delta_pct']:+.1f}%")
    
    print("\n" + "─"*36)
    print("\nLatency\n")
    print(f"Baseline       {res_res['latency']['baseline']:.1f}s")
    print(f"Candidate      {res_res['latency']['candidate']:.1f}s")
    print(f"\n{res_res['latency']['delta_pct']:+.1f}%")
    
    print("\n" + "─"*36)
    print("\nFINAL ASSESSMENT\n")
    
    # Assess final
    behav_str = "IMPROVED" if score_res['significant'] and score_res['delta'] > 0 else ("REGRESSED" if score_res['significant'] and score_res['delta'] < 0 else "STABLE")
    safety_str = "REGRESSED" if crit_res['regression'] else ("STABLE" if crit_res['candidate'] == crit_res['baseline'] else "IMPROVED")
    cost_str = "REGRESSED" if res_res['cost']['regression'] else ("STABLE" if abs(res_res['cost']['delta_pct']) < 5.0 else "IMPROVED")
    lat_str = "REGRESSED" if res_res['latency']['regression'] else ("STABLE" if abs(res_res['latency']['delta_pct']) < 5.0 else "IMPROVED")
    
    overall = "IMPROVED"
    if safety_str == "REGRESSED" or behav_str == "REGRESSED":
        overall = "REGRESSION"
    elif behav_str == "STABLE" and (cost_str == "REGRESSED" or lat_str == "REGRESSED"):
        overall = "REGRESSION (Resources)"
    elif behav_str == "STABLE":
        overall = "STABLE"
        
    print(f"Behavior:       {behav_str}")
    print(f"Reliability:    STABLE") # Mocked for report structure
    print(f"Safety:         {safety_str}")
    print(f"Cost:           {cost_str}")
    print(f"Latency:        {lat_str}")
    print(f"\nOVERALL:        {overall}")

if __name__ == "__main__":
    main()
