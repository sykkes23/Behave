import unittest
from unittest.mock import patch, MagicMock
from models.provider import ProviderConfig
from models.factory import get_provider
from models.openai import OpenAIProvider
from models.http_endpoint import HttpEndpointProvider

class TestPhase20(unittest.TestCase):
    def test_openai_adapter(self):
        config = ProviderConfig(provider_name="openai", api_key="test-key", model_name="gpt-4o")
        provider = get_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"choices":[{"message":{"content":"Hello from OpenAI!"}}], "usage":{"prompt_tokens":10,"completion_tokens":20}}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = provider.generate_response("Hello")
            self.assertEqual(res.content, "Hello from OpenAI!")
            self.assertEqual(res.usage.input_tokens, 10)
            self.assertEqual(res.usage.output_tokens, 20)

    def test_http_endpoint_adapter(self):
        config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v1/chat", api_key="test-key")
        provider = get_provider(config)
        self.assertIsInstance(provider, HttpEndpointProvider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()

            mock_resp.read.return_value = b'{"response": "Hello from custom HTTP agent!"}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = provider.generate_response("Hello")
            self.assertEqual(res.content, "Hello from custom HTTP agent!")

    def test_http_endpoint_adapter_fallback(self):
        config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v1/chat")
        provider = get_provider(config)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()

            mock_resp.read.return_value = b'Just some raw text'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = provider.generate_response("Hello")
            self.assertEqual(res.content, "Just some raw text")

if __name__ == '__main__':
    unittest.main()
