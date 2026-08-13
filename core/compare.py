import os
from typing import List, Dict, Any, Tuple
from core.baseline import load_baseline
from collections import defaultdict

def get_final_eval(run_dict: dict) -> dict:
    if "final_evaluation" in run_dict:
        return run_dict["final_evaluation"]
    return run_dict["evaluation"]

def extract_tags(failures: List[dict]) -> List[str]:
    tags = []
    for f in failures:
        if "tags" in f:
            tags.extend(f["tags"])
    return tags

def get_usage(run_dict: dict) -> Tuple[float, float, int]:
    gen_cost = 0.0
    judge_cost = 0.0
    latency = 0.0
    
    if "usage_json" in run_dict and "records" in run_dict["usage_json"]:
        for rec in run_dict["usage_json"]["records"]:
            if rec.get("role") == "generation":
                gen_cost += rec.get("cost_usd") or 0.0
                latency += rec.get("usage", {}).get("latency_ms") or 0.0
            elif rec.get("role") == "judge":
                judge_cost += rec.get("cost_usd") or 0.0
                
    # Also sum from turns if session
    if "turns" in run_dict:
        for t in run_dict["turns"]:
            if "usage_json" in t and "records" in t["usage_json"]:
                for rec in t["usage_json"]["records"]:
                    if rec.get("role") == "generation":
                        gen_cost += rec.get("cost_usd") or 0.0
                        latency += rec.get("usage", {}).get("latency_ms") or 0.0
                    elif rec.get("role") == "judge":
                        judge_cost += rec.get("cost_usd") or 0.0
                        
    return gen_cost, judge_cost, latency

def check_infrastructure_failure(run_dict: dict) -> int:
    fails = 0
    if run_dict.get("provider_status", "SUCCESS") != "SUCCESS":
        fails += 1
    if "turns" in run_dict:
        for t in run_dict["turns"]:
            if t.get("provider_status", "SUCCESS") != "SUCCESS":
                fails += 1
    return fails

def compare_baselines(baseline_name: str, candidate_name: str):
    b_manifest, b_runs, b_sessions = load_baseline(baseline_name)
    c_manifest, c_runs, c_sessions = load_baseline(candidate_name)
    
    # Organize by test_id
    b_map = {}
    for r in b_runs + b_sessions:
        b_map[r["test_id"]] = r
        
    c_map = {}
    for r in c_runs + c_sessions:
        c_map[r["test_id"]] = r
        
    common_tests = set(b_map.keys()).intersection(set(c_map.keys()))
    
    if not common_tests:
        print("No common tests found between baseline and candidate.")
        return
        
    # Aggregate Stats
    stats_b = {"score": 0.0, "critical": 0, "cost": 0.0, "latency": 0.0, "infra": 0, "tags": defaultdict(int)}
    stats_c = {"score": 0.0, "critical": 0, "cost": 0.0, "latency": 0.0, "infra": 0, "tags": defaultdict(int)}
    
    improvements = []
    regressions = []
    
    for tid in common_tests:
        br = b_map[tid]
        cr = c_map[tid]
        
        beval = get_final_eval(br)
        ceval = get_final_eval(cr)
        
        # Base stats
        stats_b["score"] += beval.get("score", 0.0)
        stats_c["score"] += ceval.get("score", 0.0)
        
        b_crit = sum(1 for f in beval.get("failures", []) if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
        c_crit = sum(1 for f in ceval.get("failures", []) if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
        
        stats_b["critical"] += b_crit
        stats_c["critical"] += c_crit
        
        # Tags
        btags = extract_tags(beval.get("failures", []))
        ctags = extract_tags(ceval.get("failures", []))
        
        for t in btags: stats_b["tags"][t] += 1
        for t in ctags: stats_c["tags"][t] += 1
        
        # Cost & Latency
        bg, bj, bl = get_usage(br)
        cg, cj, cl = get_usage(cr)
        
        stats_b["cost"] += bg + bj
        stats_c["cost"] += cg + cj
        stats_b["latency"] += bl / 1000.0  # to seconds
        stats_c["latency"] += cl / 1000.0
        
        stats_b["infra"] += check_infrastructure_failure(br)
        stats_c["infra"] += check_infrastructure_failure(cr)
        
        # Diffing Logic
        b_passed = beval.get("passed", False)
        c_passed = ceval.get("passed", False)
        
        traj_b = beval.get("trajectory", "UNKNOWN")
        traj_c = ceval.get("trajectory", "UNKNOWN")
        
        if b_passed and not c_passed:
            # Behavioral Regression
            reason = ceval.get("reasoning", "")
            regressions.append({
                "test_id": tid,
                "type": "Behavioral Regression",
                "b_status": "PASS", "c_status": "FAIL",
                "b_traj": traj_b, "c_traj": traj_c,
                "reason": reason
            })
        elif not b_passed and c_passed:
            # Improvement
            reason = ceval.get("reasoning", "")
            improvements.append({
                "test_id": tid,
                "type": "Improvement",
                "b_status": "FAIL", "c_status": "PASS",
                "b_traj": traj_b, "c_traj": traj_c,
                "reason": reason
            })
        elif c_crit > b_crit:
            # Critical Regression
            reason = ceval.get("reasoning", "")
            regressions.append({
                "test_id": tid,
                "type": "Critical Regression",
                "b_status": f"FAIL ({b_crit} crit)", "c_status": f"FAIL ({c_crit} crit)",
                "b_traj": traj_b, "c_traj": traj_c,
                "reason": reason
            })
            
    n = len(common_tests)
    avg_score_b = stats_b["score"] / n
    avg_score_c = stats_c["score"] / n
    
    print(f"BASELINE → CANDIDATE")
    print(f"\nOverall:")
    print(f"Baseline: {avg_score_b:.1f}")
    print(f"Candidate: {avg_score_c:.1f}")
    delta = avg_score_c - avg_score_b
    print(f"Delta: {'+' if delta >= 0 else ''}{delta:.1f}")
    
    print(f"\nCritical failures:")
    print(f"Baseline: {stats_b['critical']}")
    print(f"Candidate: {stats_c['critical']}")
    if stats_c['critical'] > stats_b['critical']:
        print("STATUS: REGRESSION")
        
    print(f"\nInfrastructure failures:")
    print(f"Baseline: {stats_b['infra']}")
    print(f"Candidate: {stats_c['infra']}")
    
    print(f"\nCost:")
    print(f"Baseline: ${stats_b['cost']:.4f}")
    print(f"Candidate: ${stats_c['cost']:.4f}")
    
    print(f"\nLatency:")
    print(f"Baseline: {stats_b['latency']:.1f}s")
    print(f"Candidate: {stats_c['latency']:.1f}s")
    
    print("\n--- Failure Tags ---")
    all_tags = set(stats_b["tags"].keys()).union(set(stats_c["tags"].keys()))
    for t in sorted(all_tags):
        b_count = stats_b["tags"][t]
        c_count = stats_c["tags"][t]
        if b_count != c_count:
            print(f"\n{t}:")
            print(f"Baseline: {b_count}")
            print(f"Candidate: {c_count}")
            
    if regressions:
        print("\n" + "="*50)
        print("REGRESSIONS")
        print("="*50)
        for r in regressions:
            print(f"\n{r['test_id']} ({r['type']})")
            print(f"Baseline: {r['b_status']}")
            print(f"Candidate: {r['c_status']}")
            print(f"Trajectory: {r['b_traj']} -> {r['c_traj']}")
            print(f"Evidence: {r['reason']}")
            
    if improvements:
        print("\n" + "="*50)
        print("IMPROVEMENTS")
        print("="*50)
        for i in improvements:
            print(f"\n{i['test_id']}")
            print(f"Baseline: {i['b_status']}")
            print(f"Candidate: {i['c_status']}")
            print(f"Trajectory: {i['b_traj']} -> {i['c_traj']}")
            print(f"Reason: {i['reason']}")
