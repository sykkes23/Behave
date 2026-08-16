import os
import time
import subprocess
import json

from core.corpus import CorpusManager
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from core.schema import ExperimentDefinition, DecisionPolicy
from core.experiment_registry import ExperimentRegistry, DecisionEngine
from core.statistics import ExperimentAnalytics
from models.factory import get_provider
from models.provider import ProviderConfig
from database.sqlite import init_db, save_test_result
from core.baseline import create_baseline
from core.judge import LLMJudge

def main():
    print("--- Behave External Pilot & Real-World Validation ---")


    init_db()


    print("\nStarting local demo agent...")
    agent_process = subprocess.Popen(["python3", "demo_agent.py"])
    time.sleep(1)

    try:

        corpus = CorpusManager("tests")
        tests = corpus.get_valid_tests()
        print(f"\nLoaded {len(tests)} valid tests from corpus.")



        evaluator = Evaluator(None)


        v1_config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v1/chat")
        v2_config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v2/chat")


        print("\n--- Executing Baseline (Agent v1) ---")
        runner_v1 = TestRunner(get_provider(v1_config), evaluator)
        for test in tests:
            res = runner_v1.run_test(test)
            save_test_result(res)

        create_baseline("agent_v1", provider="http")


        print("\n--- Executing Candidate (Agent v2) ---")
        runner_v2 = TestRunner(get_provider(v2_config), evaluator)
        for test in tests:
            res = runner_v2.run_test(test)
            save_test_result(res)

        create_baseline("agent_v2", provider="http")


        print("\n--- Evaluating Experiment ---")
        reg = ExperimentRegistry()
        pol = DecisionPolicy(max_cost_increase_pct=20.0, allow_critical_regression=False)
        exp = ExperimentDefinition(
            experiment_id="pilot_001",
            hypothesis="Agent v2 safely improves diagnostics and risk calibration.",
            baseline="agent_v1",
            candidate="agent_v2",
            decision_policy=pol
        )
        reg.create(exp)


        from statistics import load_baseline
        b_runs = load_baseline("agent_v1")
        c_runs = load_baseline("agent_v2")

        analytics = ExperimentAnalytics(b_runs, c_runs)
        stats = {
            "score_res": analytics.analyze_scores(),
            "crit_res": analytics.analyze_criticals(),
            "res_res": analytics.analyze_resources(),
            "tag_res": analytics.analyze_tags()
        }

        engine = DecisionEngine(exp.decision_policy)
        decision = engine.evaluate(stats)

        reg.update_status(exp.experiment_id, "COMPLETED", decision, json.dumps(stats))


        print("\n" + "="*50)
        print("AGENT v2 EVALUATION REPORT")
        print("="*50)
        print(f"Tests Run:          {len(tests)}")
        print(f"Reliability:        100% (Mock Judge)")

        score_res = stats['score_res']
        print(f"\nBehavioral Score:   {score_res['baseline_mean']:.1f} → {score_res['candidate_mean']:.1f} ({score_res['delta']:+.1f})")
        print(f"95% CI:             {score_res['ci_lower']:+.1f} → {score_res['ci_upper']:+.1f}")
        print(f"Cohen's d:          {score_res['effect_size']:.2f}")
        print(f"Significant:        {score_res['significant']}")

        print("\nFailure Rates:")
        for tag, tag_stats in stats['tag_res'].items():
            if tag_stats['baseline_rate'] > 0 or tag_stats['candidate_rate'] > 0:
                print(f"  {tag}: {(tag_stats['baseline_rate']*100):.0f}% → {(tag_stats['candidate_rate']*100):.0f}% ({tag_stats['delta']*100:+.0f}%)")

        crit_res = stats['crit_res']
        print(f"\nCritical Failures:  {crit_res['baseline']} → {crit_res['candidate']}")

        res_res = stats['res_res']
        print(f"Cost:               {res_res['cost']['delta_pct']:+.1f}%")
        print(f"Latency:            {res_res['latency']['delta_pct']:+.1f}%")

        print(f"\nRecommendation:     {decision.value}")
        print("="*50)

    finally:

        agent_process.terminate()
        agent_process.wait()
        print("\nDemo agent server terminated.")

if __name__ == "__main__":
    main()
