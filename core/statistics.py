import math
import random
from typing import List, Dict, Tuple, Any

def mean(data: List[float]) -> float:
    if not data: return 0.0
    return sum(data) / len(data)

def variance(data: List[float], ddof: int = 1) -> float:
    if len(data) <= ddof: return 0.0
    m = mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - ddof)

def std_dev(data: List[float], ddof: int = 1) -> float:
    return math.sqrt(variance(data, ddof))

def cohens_d(data1: List[float], data2: List[float]) -> float:
    """Effect size for paired samples: mean difference / std_dev of differences"""
    if len(data1) != len(data2) or len(data1) < 2: return 0.0
    diffs = [x - y for x, y in zip(data2, data1)]
    sd = std_dev(diffs)
    if sd == 0: return 0.0
    return mean(diffs) / sd

def bootstrap_ci(data1: List[float], data2: List[float], alpha: float = 0.05, iterations: int = 1000, seed: int = 42) -> Tuple[float, float]:
    """Bootstrap confidence interval for mean of differences (data2 - data1)"""
    if len(data1) != len(data2) or len(data1) == 0: return (0.0, 0.0)
    diffs = [x - y for x, y in zip(data2, data1)]
    n = len(diffs)
    rng = random.Random(seed)
    
    boot_means = []
    for _ in range(iterations):
        sample = [rng.choice(diffs) for _ in range(n)]
        boot_means.append(mean(sample))
        
    boot_means.sort()
    lower_idx = int(iterations * (alpha / 2))
    upper_idx = int(iterations * (1 - alpha / 2))
    
    return boot_means[lower_idx], boot_means[upper_idx]

def mcnemar_test(b_pass: List[bool], c_pass: List[bool]) -> float:
    """
    McNemar's test for paired binary data.
    Returns p-value (approximate via chi-square distribution with 1 df).
    """
    if len(b_pass) != len(c_pass): return 1.0
    
    b_pass_c_fail = 0
    b_fail_c_pass = 0
    
    for b, c in zip(b_pass, c_pass):
        if b and not c:
            b_pass_c_fail += 1
        elif not b and c:
            b_fail_c_pass += 1
            
    b = b_pass_c_fail
    c = b_fail_c_pass
    
    if b + c == 0: return 1.0
    
    chi_square = ((abs(b - c) - 1) ** 2) / (b + c)
    
    # Simple chi-square to p-value approximation for 1 df
    return _chisquare_1df_pvalue(chi_square)

def _chisquare_1df_pvalue(chi_sq: float) -> float:
    # Very crude approximation of chi-square survival function for 1 DOF
    # Accurate enough for p < 0.05 checks
    if chi_sq <= 0: return 1.0
    import math
    try:
        from math import erfc
        return erfc(math.sqrt(chi_sq / 2.0))
    except:
        return 0.0

def benjamini_hochberg(p_values: List[float]) -> List[float]:
    """
    Benjamini-Hochberg FDR correction.
    Returns adjusted p-values.
    """
    if not p_values: return []
    
    n = len(p_values)
    # Store original indices
    indexed_p = list(enumerate(p_values))
    # Sort by p-value ascending
    indexed_p.sort(key=lambda x: x[1])
    
    adj_p = [0.0] * n
    min_adj = 1.0
    
    # Process from highest p-value to lowest to ensure monotonicity
    for i in range(n - 1, -1, -1):
        orig_idx, p = indexed_p[i]
        rank = i + 1
        adj = (p * n) / rank
        min_adj = min(min_adj, adj)
        adj_p[orig_idx] = min(min_adj, 1.0)
        
    return adj_p

def is_significant(ci_lower: float, ci_upper: float) -> bool:
    """Check if 0 is outside the confidence interval"""
    return not (ci_lower <= 0 <= ci_upper)

class ExperimentAnalytics:
    def __init__(self, baseline_runs: Dict[str, Any], candidate_runs: Dict[str, Any]):
        self.baseline = baseline_runs
        self.candidate = candidate_runs
        self.paired_tests = self._get_paired_tests()
        
    def _get_paired_tests(self) -> List[str]:
        return sorted(list(set(self.baseline.keys()) & set(self.candidate.keys())))
        
    def analyze_scores(self) -> Dict[str, Any]:
        b_scores = []
        c_scores = []
        for tid in self.paired_tests:
            b_scores.append(self.baseline[tid].get("score", 0.0))
            c_scores.append(self.candidate[tid].get("score", 0.0))
            
        b_mean = mean(b_scores)
        c_mean = mean(c_scores)
        delta = c_mean - b_mean
        
        ci_lower, ci_upper = bootstrap_ci(b_scores, c_scores)
        eff_size = cohens_d(b_scores, c_scores)
        
        return {
            "baseline_mean": b_mean,
            "candidate_mean": c_mean,
            "delta": delta,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "effect_size": eff_size,
            "significant": is_significant(ci_lower, ci_upper)
        }
        
    def analyze_tags(self) -> Dict[str, Any]:
        # Gather all tags across both
        all_tags = set()
        b_tag_hits = {tid: set() for tid in self.paired_tests}
        c_tag_hits = {tid: set() for tid in self.paired_tests}
        
        for tid in self.paired_tests:
            b_fails = self.baseline[tid].get("failures", [])
            for f in b_fails:
                for tag in f.get("tags", []):
                    all_tags.add(tag)
                    b_tag_hits[tid].add(tag)
                    
            c_fails = self.candidate[tid].get("failures", [])
            for f in c_fails:
                for tag in f.get("tags", []):
                    all_tags.add(tag)
                    c_tag_hits[tid].add(tag)
                    
        results = {}
        tags_list = list(all_tags)
        p_values = []
        
        for tag in tags_list:
            b_pass = [tag not in b_tag_hits[tid] for tid in self.paired_tests]
            c_pass = [tag not in c_tag_hits[tid] for tid in self.paired_tests]
            
            b_rate = 1.0 - mean([float(p) for p in b_pass])
            c_rate = 1.0 - mean([float(p) for p in c_pass])
            
            p_val = mcnemar_test(b_pass, c_pass)
            p_values.append(p_val)
            
            results[tag] = {
                "baseline_rate": b_rate,
                "candidate_rate": c_rate,
                "delta": c_rate - b_rate,
                "raw_p": p_val
            }
            
        adj_p_values = benjamini_hochberg(p_values)
        for tag, adj_p in zip(tags_list, adj_p_values):
            results[tag]["adj_p"] = adj_p
            results[tag]["significant"] = adj_p < 0.05
            
        return results

    def analyze_criticals(self) -> Dict[str, Any]:
        b_crit = 0
        c_crit = 0
        for tid in self.paired_tests:
            b_crit += sum(1 for f in self.baseline[tid].get("failures", []) if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
            c_crit += sum(1 for f in self.candidate[tid].get("failures", []) if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
            
        return {
            "baseline": b_crit,
            "candidate": c_crit,
            "regression": c_crit > b_crit
        }
        
    def analyze_resources(self) -> Dict[str, Any]:
        b_cost = 0.0
        c_cost = 0.0
        b_lat = 0.0
        c_lat = 0.0
        
        for tid in self.paired_tests:
            b_cost += self.baseline[tid].get("cost", 0.0)
            c_cost += self.candidate[tid].get("cost", 0.0)
            b_lat += self.baseline[tid].get("latency", 0.0)
            c_lat += self.candidate[tid].get("latency", 0.0)
            
        return {
            "cost": {
                "baseline": b_cost,
                "candidate": c_cost,
                "delta_pct": ((c_cost - b_cost) / b_cost * 100.0) if b_cost > 0 else 0.0,
                "regression": c_cost > b_cost * 1.05  # >5% increase is a regression
            },
            "latency": {
                "baseline": b_lat,
                "candidate": c_lat,
                "delta_pct": ((c_lat - b_lat) / b_lat * 100.0) if b_lat > 0 else 0.0,
                "regression": c_lat > b_lat * 1.05
            }
        }
