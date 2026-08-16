import os
import unittest
import json
import shutil

from core.statistics import (
    mean, variance, std_dev, cohens_d, bootstrap_ci, mcnemar_test, benjamini_hochberg, is_significant, ExperimentAnalytics
)

class TestPhase17(unittest.TestCase):
    def test_basic_stats(self):
        data = [1, 2, 3, 4, 5]
        self.assertEqual(mean(data), 3.0)
        self.assertAlmostEqual(variance(data), 2.5)
        self.assertAlmostEqual(std_dev(data), 1.5811388, places=4)

    def test_cohens_d(self):

        d1 = [1, 2, 3]
        d2 = [2, 3, 4]

        self.assertEqual(cohens_d(d1, d2), 0.0)

        d1 = [1, 2, 3, 4]
        d2 = [3, 4, 4, 6]


        self.assertAlmostEqual(cohens_d(d1, d2), 3.5, places=1)

    def test_bootstrap_ci(self):
        d1 = [82, 85, 80, 78, 81]
        d2 = [85, 88, 83, 85, 86]

        lower, upper = bootstrap_ci(d1, d2, seed=42)
        self.assertTrue(lower > 0)
        self.assertTrue(upper > 0)
        self.assertTrue(is_significant(lower, upper))

    def test_mcnemar(self):
        b_pass = [True, True, False, False, False, True]
        c_pass = [True, True, True,  True,  False, False]



        p = mcnemar_test(b_pass, c_pass)
        self.assertEqual(p, 1.0)


        b2 = [False]*10 + [True]*10
        c2 = [True]*10 + [True]*10

        p2 = mcnemar_test(b2, c2)
        self.assertLess(p2, 0.05)

    def test_benjamini_hochberg(self):
        p_vals = [0.01, 0.04, 0.03, 0.005]
        adj = benjamini_hochberg(p_vals)




        self.assertEqual(adj, [0.02, 0.04, 0.04, 0.02])

    def test_experiment_analytics(self):
        b = {
            "t1": {"score": 80, "failures": [{"severity": "LOW"}], "cost": 1.0, "latency": 1.0},
            "t2": {"score": 70, "failures": [{"severity": "CRITICAL", "tags": ["hallucination"]}], "cost": 1.0, "latency": 1.0},
            "t3": {"score": 90, "failures": [], "cost": 1.0, "latency": 1.0},
            "t4": {"score": 60, "failures": [], "cost": 1.0, "latency": 1.0},
            "t5": {"score": 75, "failures": [], "cost": 1.0, "latency": 1.0}
        }
        c = {
            "t1": {"score": 90, "failures": [], "cost": 1.5, "latency": 1.2},
            "t2": {"score": 85, "failures": [{"severity": "LOW", "tags": ["hallucination"]}], "cost": 1.5, "latency": 1.2},
            "t3": {"score": 90, "failures": [], "cost": 1.5, "latency": 1.2},
            "t4": {"score": 80, "failures": [], "cost": 1.5, "latency": 1.2},
            "t5": {"score": 85, "failures": [], "cost": 1.5, "latency": 1.2}
        }

        ea = ExperimentAnalytics(b, c)

        s = ea.analyze_scores()
        self.assertEqual(s["baseline_mean"], 75.0)
        self.assertEqual(s["candidate_mean"], 86.0)
        self.assertTrue(s["significant"])

        crit = ea.analyze_criticals()
        self.assertEqual(crit["baseline"], 1)
        self.assertEqual(crit["candidate"], 0)
        self.assertFalse(crit["regression"])

        tags = ea.analyze_tags()
        self.assertIn("hallucination", tags)

        res = ea.analyze_resources()
        self.assertEqual(res["cost"]["baseline"], 5.0)
        self.assertEqual(res["cost"]["candidate"], 7.5)
        self.assertEqual(res["cost"]["delta_pct"], 50.0)
        self.assertTrue(res["cost"]["regression"])

if __name__ == '__main__':
    unittest.main()
