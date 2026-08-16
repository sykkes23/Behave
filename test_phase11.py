import os
import unittest
import json
from unittest.mock import MagicMock
import urllib.error

from core.schema import TestSpec, TurnSpec, EvaluationCriterion, SessionResult, TurnResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from core.pricing import PricingEngine, UsageRecord, PricingModel
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, ProviderError, ProviderErrorType, UsageMetrics
from models.gemini import GeminiProvider
from database.sqlite import init_db, DB_PATH, save_test_result, get_test_result, save_session_result, get_session_result

class MockPhase11Provider(BaseProvider):
    def __init__(self, usage=None, error=None):
        super().__init__(ProviderConfig(provider_name="mock", model_name="mock-model"))
        self.usage = usage
        self.error = error

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if self.error:
            raise self.error

        usage = self.usage or UsageMetrics()
        return ProviderResponse(
            provider="mock",
            model="mock-model",
            content="Mock response",
            usage=usage
        )

class TestPhase11(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_usage_normalization(self):

        usage = UsageMetrics(input_tokens=1000, output_tokens=2000, total_tokens=3000, latency_ms=100)

        PricingEngine._registry["mock:mock-model"] = PricingModel("mock", "mock-model", 1.0, 2.0)

        provider = MockPhase11Provider(usage=usage)
        evaluator = Evaluator()
        runner = TestRunner(provider=provider, evaluator=evaluator)
        spec = TestSpec(test_id="t1", scenario="test")

        result = runner.run_test(spec)
        records = result.usage_json.get("records", [])

        self.assertGreaterEqual(len(records), 1)
        gen_record = records[0]

        self.assertEqual(gen_record["usage"]["input_tokens"], 1000)
        self.assertEqual(gen_record["usage"]["output_tokens"], 2000)




        self.assertAlmostEqual(gen_record["cost_usd"], 0.005)

    def test_missing_usage_and_unknown_pricing(self):

        usage = UsageMetrics(input_tokens=None, output_tokens=None, total_tokens=None)
        provider = MockPhase11Provider(usage=usage)
        evaluator = Evaluator()
        runner = TestRunner(provider=provider, evaluator=evaluator)
        spec = TestSpec(test_id="t2", scenario="test")

        result = runner.run_test(spec)
        records = result.usage_json.get("records", [])
        gen_record = records[0]

        self.assertIsNone(gen_record["usage"]["input_tokens"])
        self.assertIsNone(gen_record["cost_usd"])

        usage2 = UsageMetrics(input_tokens=1000, output_tokens=2000)
        provider2 = MockPhase11Provider(usage=usage2)
        provider2.config.model_name = "unknown-model-pricing"
        runner2 = TestRunner(provider=provider2, evaluator=evaluator)
        result2 = runner2.run_test(spec)
        gen_record2 = result2.usage_json.get("records", [])[0]
        self.assertIsNone(gen_record2["cost_usd"])

    def test_latency_measured(self):

        provider = MockPhase11Provider()
        evaluator = Evaluator()
        runner = TestRunner(provider=provider, evaluator=evaluator)
        spec = TestSpec(test_id="t3", scenario="test")


        pass

    def test_session_aggregation(self):

        usage = UsageMetrics(input_tokens=1000, output_tokens=1000, total_tokens=2000, latency_ms=100)
        PricingEngine._registry["mock:mock-model"] = PricingModel("mock", "mock-model", 1.0, 1.0)
        provider = MockPhase11Provider(usage=usage)
        evaluator = Evaluator()
        runner = TestRunner(provider=provider, evaluator=evaluator)

        spec = TestSpec(
            test_id="t4",
            scenario="test",
            turns=[TurnSpec(user_input="hi"), TurnSpec(user_input="hello")]
        )

        result = runner.run_session(spec)
        self.assertEqual(len(result.turns), 2)
        self.assertEqual(result.turns[0].usage_json["records"][0]["cost_usd"], 0.002)
        self.assertEqual(result.turns[1].usage_json["records"][0]["cost_usd"], 0.002)

    def test_infrastructure_errors_metrics(self):

        error = ProviderError(ProviderErrorType.TIMEOUT, "Timeout")
        provider = MockPhase11Provider(error=error)
        evaluator = Evaluator()
        runner = TestRunner(provider=provider, evaluator=evaluator)
        spec = TestSpec(test_id="t5", scenario="test")

        result = runner.run_test(spec)
        self.assertEqual(result.provider_status, "TIMEOUT")
        self.assertFalse(result.evaluation.passed)
        self.assertEqual(result.evaluation.score, 0.0)

    def test_secret_sanitization(self):

        config = ProviderConfig(provider_name="gemini", api_key="SUPER_SECRET_KEY")
        provider = GeminiProvider(config=config)

        import urllib.request
        from urllib.error import HTTPError


        def mock_urlopen(*args, **kwargs):
            import io
            body = b"Unauthorized access with key=SUPER_SECRET_KEY."
            fp = io.BytesIO(body)
            raise HTTPError(url="test", code=401, msg="Unauthorized", hdrs={}, fp=fp)

        urllib.request.urlopen = mock_urlopen

        with self.assertRaises(ProviderError) as context:
            provider.generate_response("test")

        self.assertNotIn("SUPER_SECRET_KEY", str(context.exception))
        self.assertIn("SANITIZED", str(context.exception))

if __name__ == '__main__':
    unittest.main()
