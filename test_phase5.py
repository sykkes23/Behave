import os
import unittest
import time
from unittest.mock import patch, MagicMock
from core.schema import TestSpec
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.provider import ProviderConfig
from models.factory import get_provider
from database.sqlite import init_db, get_test_result, DB_PATH
import json

class TestPhase5(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        
        self.spec = TestSpec(
            test_id="test_005",
            test_version="v1",
            scenario="Diagnostic scenario"
        )
        self.evaluator = Evaluator()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_multi_provider_execution(self):
        # 1 & 2. Execute same test against different providers without changing the test definition
        # We will use 'mock' and a mocked 'gemini' 
        
        # Run mock
        config_mock = ProviderConfig(provider_name="mock", model_name="mock-v1")
        provider_mock = get_provider(config_mock, {"diagnostic": "mock response"})
        runner_mock = TestRunner(provider=provider_mock, evaluator=self.evaluator)
        result_mock = runner_mock.run_test(self.spec)
        
        # 4 & 6. Metadata validation for Mock
        self.assertEqual(result_mock.metadata.provider, "mock")
        self.assertEqual(result_mock.metadata.model, "mock-v1")
        self.assertNotIn("api_key", result_mock.metadata.configuration_hash)
        
        # Run mocked Gemini
        config_gemini = ProviderConfig(provider_name="gemini", api_key="test-key")
        provider_gemini = get_provider(config_gemini)
        
        # Patch the URL open so it doesn't actually hit the internet
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'''
            {
                "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10, "totalTokenCount": 15},
                "modelVersion": "gemini-1.5-flash-test"
            }
            '''
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            
            runner_gemini = TestRunner(provider=provider_gemini, evaluator=self.evaluator)
            result_gemini = runner_gemini.run_test(self.spec)
            
        # 3. Unique run_id, same test definition
        self.assertNotEqual(result_mock.run_id, result_gemini.run_id)
        self.assertEqual(result_mock.test_id, result_gemini.test_id)
        
        # 4. Metadata validation for Gemini
        self.assertEqual(result_gemini.metadata.provider, "gemini")
        self.assertEqual(result_gemini.metadata.model_version, "gemini-1.5-flash-test")
        
    def test_provider_errors_isolated(self):
        # 5. API failures remain provider errors
        config_gemini = ProviderConfig(provider_name="gemini", api_key="bad-key")
        provider_gemini = get_provider(config_gemini)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            import urllib.error
            import io
            fp = io.BytesIO(b'{"error": "invalid API key"}')
            err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=fp)
            mock_urlopen.side_effect = err
            
            runner = TestRunner(provider=provider_gemini, evaluator=self.evaluator)
            result = runner.run_test(self.spec)
            
            self.assertTrue(result.evaluation.passed)
            self.assertEqual(len(result.evaluation.failures), 1)
            self.assertEqual(result.evaluation.failures[0].tags, ["AUTH_ERROR"])
            # Ensure it didn't just throw an exception and crash, but encapsulated it properly
            self.assertEqual(result.metadata.provider, "gemini")

if __name__ == '__main__':
    unittest.main()
