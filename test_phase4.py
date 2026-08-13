import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io

from core.schema import TestSpec, EvaluationCriterion, EvaluationResult
from models.provider import BaseProvider, ProviderResponse, ProviderConfig, UsageMetrics, ProviderError, ProviderErrorType
from models.factory import get_provider
from models.mock import MockAIModel
from models.gemini import GeminiProvider
from models.venice import VeniceProvider
from core.metadata import sanitize_config

class TestPhase4(unittest.TestCase):
    def test_provider_selection_and_mock(self):
        # 2 & 3. Mock provider compatibility and selection
        config = ProviderConfig(provider_name="mock", model_name="mock-v1")
        provider = get_provider(config, {"hello": "world"})
        
        self.assertIsInstance(provider, MockAIModel)
        
        # 1 & 4. Provider interface and normalized structure
        response = provider.generate_response("hello")
        self.assertEqual(response.provider, "mock")
        self.assertEqual(response.model, "mock-v1")
        self.assertEqual(response.content, "world")
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertIsNotNone(response.usage.latency_ms)

    def test_config_sanitization(self):
        # 6. Configuration sanitization
        config = ProviderConfig(provider_name="gemini", api_key="sk-real-secret")
        sanitized = sanitize_config(config.as_dict())
        self.assertEqual(sanitized["api_key"], "***REDACTED***")

    @patch('urllib.request.urlopen')
    def test_gemini_adapter(self, mock_urlopen):
        # 7. Gemini adapter using mocked HTTP/API responses
        mock_response = MagicMock()
        mock_response.read.return_value = b'''
        {
            "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10, "totalTokenCount": 15},
            "modelVersion": "gemini-1.5-flash-001"
        }
        '''
        # Needs to act as a context manager
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        config = ProviderConfig(provider_name="gemini", api_key="test-key")
        provider = get_provider(config)
        self.assertIsInstance(provider, GeminiProvider)
        
        response = provider.generate_response("test prompt")
        self.assertEqual(response.provider, "gemini")
        self.assertEqual(response.content, "Gemini response")
        self.assertEqual(response.usage.input_tokens, 5)
        self.assertEqual(response.model_version, "gemini-1.5-flash-001")

    @patch('urllib.request.urlopen')
    def test_venice_adapter(self, mock_urlopen):
        # 8. Venice adapter using mocked HTTP/API responses
        mock_response = MagicMock()
        mock_response.read.return_value = b'''
        {
            "id": "req-123",
            "model": "llama-3",
            "choices": [{"message": {"content": "Venice response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
        }
        '''
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        config = ProviderConfig(provider_name="venice", api_key="test-key", model_name="llama-3")
        provider = get_provider(config)
        self.assertIsInstance(provider, VeniceProvider)
        
        response = provider.generate_response("test prompt")
        self.assertEqual(response.provider, "venice")
        self.assertEqual(response.content, "Venice response")
        self.assertEqual(response.usage.input_tokens, 5)
        self.assertEqual(response.model, "llama-3")
        self.assertEqual(response.request_id, "req-123")
        self.assertEqual(response.model_version, "unknown")

    @patch('urllib.request.urlopen')
    def test_provider_errors(self, mock_urlopen):
        # 5. Provider error normalization
        # Simulate a 401 Unauthorized
        fp = io.BytesIO(b'{"error": "invalid API key"}')
        err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=fp)
        mock_urlopen.side_effect = err
        
        config = ProviderConfig(provider_name="gemini", api_key="bad-key")
        provider = get_provider(config)
        
        with self.assertRaises(ProviderError) as context:
            provider.generate_response("test")
            
        self.assertEqual(context.exception.error_type, ProviderErrorType.AUTH_ERROR)

if __name__ == '__main__':
    unittest.main()
