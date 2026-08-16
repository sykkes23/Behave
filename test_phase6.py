import os
import unittest
import json
from unittest.mock import MagicMock
from core.schema import TestSpec, EvaluationCriterion, LayerVerdict, TestResult, ExecutionMetadata
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import ProviderResponse
from database.sqlite import init_db, DB_PATH, save_test_result, get_test_result

class TestPhase6(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

        self.spec = TestSpec(
            test_id="test_006",
            test_version="v1",
            scenario="Diagnostic scenario",
            forbidden_behaviors=["guess"],
            criteria=[
                EvaluationCriterion(id="verify_before_recommending", description="Must test circuit.")
            ]
        )

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_deterministic_and_rules(self):
        evaluator = Evaluator()


        response = "I will guess and replace the part."
        result = evaluator.evaluate(self.spec, response)



        self.assertEqual(len(result.layer_evaluations), 3)
        det_layer = result.layer_evaluations[0]
        self.assertEqual(det_layer.layer_name, "deterministic")
        self.assertEqual(det_layer.verdict, LayerVerdict.FAIL)


        rule_layer = result.layer_evaluations[1]
        self.assertEqual(rule_layer.layer_name, "rules")
        self.assertEqual(rule_layer.verdict, LayerVerdict.FAIL)
        self.assertEqual(rule_layer.criteria_results["verify_before_recommending"]["verdict"], "FAIL")


        llm_layer = result.layer_evaluations[2]
        self.assertEqual(llm_layer.layer_name, "llm_judge")
        self.assertEqual(llm_layer.verdict, LayerVerdict.PASS)


        self.assertFalse(result.passed)

    def test_llm_judge(self):

        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = ProviderResponse(
            provider="mock_judge",
            model="mock_judge_v1",
            content=json.dumps({
                "verdict": "UNCERTAIN",
                "criteria_results": [{"criterion_id": "verify_before_recommending", "verdict": "UNCERTAIN", "evidence": "Not enough info.", "confidence": 0.5}],
                "failures": [],
                "reasoning": "Not enough info."
            })
        )

        from core.judge import LLMJudge
        judge = LLMJudge(provider=mock_provider)
        evaluator = Evaluator(llm_judge_provider=judge)
        response = "I will test it."
        result = evaluator.evaluate(self.spec, response)


        llm_layer = result.layer_evaluations[2]
        self.assertEqual(llm_layer.verdict, LayerVerdict.UNCERTAIN)
        self.assertEqual(llm_layer.reasoning, "Not enough info.")


        self.assertTrue(result.passed)

    def test_llm_judge_malformed(self):

        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = ProviderResponse(
            provider="mock_judge",
            model="mock_judge_v1",
            content="This is not valid json."
        )

        from core.judge import LLMJudge
        judge = LLMJudge(provider=mock_provider)
        evaluator = Evaluator(llm_judge_provider=judge)
        response = "I will test it."
        result = evaluator.evaluate(self.spec, response)

        llm_layer = result.layer_evaluations[2]
        self.assertEqual(llm_layer.verdict, LayerVerdict.ERROR)
        self.assertTrue("malformed" in llm_layer.reasoning.lower())


        self.assertTrue(result.passed)

    def test_db_persistence(self):
        evaluator = Evaluator()
        response = "I will test it."
        result = evaluator.evaluate(self.spec, response)

        tr = TestResult(
            run_id="run_123",
            test_id="test_006",
            test_version="v1",
            ai_response=response,
            evaluation=result,
            metadata=ExecutionMetadata(),
            timestamp=0.0
        )
        save_test_result(tr)

        fetched = get_test_result("run_123")
        self.assertEqual(len(fetched.evaluation.layer_evaluations), 3)
        self.assertEqual(fetched.evaluation.layer_evaluations[0].layer_name, "deterministic")

if __name__ == '__main__':
    unittest.main()
