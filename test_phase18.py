import os
import unittest
import shutil

from core.schema import ExperimentDefinition, DecisionPolicy, FinalDecision
from core.experiment_registry import ExperimentRegistry, DecisionEngine

class TestPhase18(unittest.TestCase):
    def setUp(self):
        self.reg_dir = "temp_registry"
        if os.path.exists(self.reg_dir):
            shutil.rmtree(self.reg_dir)
        os.makedirs(self.reg_dir)
        self.reg = ExperimentRegistry(self.reg_dir)

    def tearDown(self):
        if os.path.exists(self.reg_dir):
            shutil.rmtree(self.reg_dir)

    def test_experiment_creation(self):
        exp = ExperimentDefinition(
            experiment_id="exp_123",
            hypothesis="Testing prompt V2",
            baseline="v1",
            candidate="v2"
        )
        self.reg.create(exp)

        loaded = self.reg.get("exp_123")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.hypothesis, "Testing prompt V2")
        self.assertEqual(loaded.status, "PLANNED")
        self.assertTrue(loaded.created_at > 0)

    def test_decision_engine(self):
        pol = DecisionPolicy(max_cost_increase_pct=10.0, allow_critical_regression=False)
        engine = DecisionEngine(pol)


        stats_good = {
            "score_res": {"significant": True, "delta": 5.0},
            "crit_res": {"regression": False},
            "res_res": {"cost": {"delta_pct": 5.0}, "latency": {"delta_pct": 0.0}}
        }
        self.assertEqual(engine.evaluate(stats_good), FinalDecision.DEPLOY)


        stats_crit = {
            "score_res": {"significant": True, "delta": 10.0},
            "crit_res": {"regression": True},
            "res_res": {"cost": {"delta_pct": -5.0}, "latency": {"delta_pct": 0.0}}
        }
        self.assertEqual(engine.evaluate(stats_crit), FinalDecision.BLOCKED)


        stats_bad = {
            "score_res": {"significant": True, "delta": -2.0},
            "crit_res": {"regression": False},
            "res_res": {"cost": {"delta_pct": 0.0}, "latency": {"delta_pct": 0.0}}
        }
        self.assertEqual(engine.evaluate(stats_bad), FinalDecision.REGRESSION)


        stats_expensive = {
            "score_res": {"significant": True, "delta": 2.0},
            "crit_res": {"regression": False},
            "res_res": {"cost": {"delta_pct": 50.0}, "latency": {"delta_pct": 0.0}}
        }

        self.assertEqual(engine.evaluate(stats_expensive), FinalDecision.CONDITIONAL)


        stats_stable_expensive = {
            "score_res": {"significant": False, "delta": 0.5},
            "crit_res": {"regression": False},
            "res_res": {"cost": {"delta_pct": 50.0}, "latency": {"delta_pct": 0.0}}
        }
        self.assertEqual(engine.evaluate(stats_stable_expensive), FinalDecision.REGRESSION)

    def test_experiment_lifecycle(self):
        exp = ExperimentDefinition(
            experiment_id="exp_flow",
            hypothesis="x",
            baseline="b",
            candidate="c"
        )
        self.reg.create(exp)


        updated = self.reg.update_status("exp_flow", "COMPLETED", FinalDecision.CONDITIONAL, '{"some":"stats"}')
        self.assertEqual(updated.status, "COMPLETED")
        self.assertEqual(updated.final_decision, FinalDecision.CONDITIONAL)
        self.assertIsNotNone(updated.completed_at)


        all_exps = self.reg.list_all()
        self.assertEqual(len(all_exps), 1)
        self.assertEqual(all_exps[0].experiment_id, "exp_flow")

if __name__ == '__main__':
    unittest.main()
