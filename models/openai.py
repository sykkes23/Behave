import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any

from .provider import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType, ProviderConfig, UsageMetrics

class OpenAIProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model_name if config.model_name and config.model_name != "unknown" else "gpt-4o"
        self.base_url = config.api_base if config.api_base else "https://api.openai.com/v1"

    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(ProviderErrorType.AUTH_ERROR, "OpenAI API key is missing.")

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        messages = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

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
            with urllib.request.urlopen(req) as response:
                latency = time.monotonic() - start_time
                resp_body = response.read().decode('utf-8')
                data = json.loads(resp_body)

                content = data["choices"][0]["message"]["content"]

                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)


                metrics = UsageMetrics(
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency * 1000
                )

                return ProviderResponse(
                    provider="openai",
                    model=self.model,
                    content=content,
                    usage=metrics,
                    provider_metadata=data
                )

        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            msg = f"HTTP {e.code}: {err_body}"
            msg = sanitize(msg)

            if e.code == 429:
                raise ProviderError(ProviderErrorType.RATE_LIMIT, msg)
            elif e.code in (401, 403):
                raise ProviderError(ProviderErrorType.AUTH_ERROR, msg)
            elif e.code == 400:
                raise ProviderError(ProviderErrorType.INVALID_REQUEST, msg)
            else:
                raise ProviderError(ProviderErrorType.PROVIDER_ERROR, msg)
        except urllib.error.URLError as e:
            raise ProviderError(ProviderErrorType.PROVIDER_ERROR, sanitize(str(e)))
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN_PROVIDER_ERROR, sanitize(str(e)))
