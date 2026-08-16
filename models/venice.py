import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any

from .provider import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType, ProviderConfig, UsageMetrics

class VeniceProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key

        self.model = config.model_name if config.model_name and config.model_name != "unknown" else "venice-default"

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(ProviderErrorType.AUTH_ERROR, "Venice API key is missing.")

        url = "https://api.venice.ai/api/v1/chat/completions"

        messages = []
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature
        }
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {self.api_key}')

        start_time = time.monotonic()

        def sanitize(text: str) -> str:
            if self.api_key and self.api_key in text:
                return text.replace(self.api_key, "***SANITIZED***")
            return text

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                latency_ms = (time.monotonic() - start_time) * 1000
                response_data = json.loads(response.read().decode('utf-8'))

                content = response_data['choices'][0]['message']['content']
                usage = response_data.get('usage', {})
                input_tokens = usage.get('prompt_tokens')
                output_tokens = usage.get('completion_tokens')
                total_tokens = usage.get('total_tokens')

                request_id = response_data.get('id')

                model_used = response_data.get('model', self.model)

                return ProviderResponse(
                    provider="venice",
                    model=model_used,
                    content=content,
                    request_id=request_id,
                    usage=UsageMetrics(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        latency_ms=latency_ms,
                        time_to_first_token_ms=None
                    ),
                    model_version="unknown"
                )

        except urllib.error.HTTPError as e:
            err_body = sanitize(e.read().decode('utf-8'))
            if e.code == 401 or e.code == 403:
                raise ProviderError(ProviderErrorType.AUTH_ERROR, f"Authentication failed: {err_body}")
            elif e.code == 429:
                raise ProviderError(ProviderErrorType.RATE_LIMIT, f"Rate limit exceeded: {err_body}")
            elif e.code == 400:
                raise ProviderError(ProviderErrorType.INVALID_REQUEST, f"Invalid request: {err_body}")
            else:
                raise ProviderError(ProviderErrorType.PROVIDER_ERROR, f"HTTP {e.code}: {err_body}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ProviderError(ProviderErrorType.TIMEOUT, "Request to Venice timed out.")
            raise ProviderError(ProviderErrorType.PROVIDER_ERROR, f"Network error: {sanitize(str(e))}")
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN_PROVIDER_ERROR, f"Unexpected error: {sanitize(str(e))}")
