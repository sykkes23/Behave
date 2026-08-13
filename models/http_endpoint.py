import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any

from .provider import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType, ProviderConfig, UsageMetrics

class HttpEndpointProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.url = config.api_base
        self.api_key = config.api_key
        
    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if not self.url:
            raise ProviderError(ProviderErrorType.MALFORMED_REQUEST, "HTTP endpoint URL is missing in api_base.")
            
        payload = {
            "prompt": prompt,
            "history": history or []
        }
        
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode('utf-8'), method='POST')
        req.add_header('Content-Type', 'application/json')
        if self.api_key:
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
                
                try:
                    data = json.loads(resp_body)
                    content = data.get("response", data.get("content", data.get("text", resp_body)))
                except json.JSONDecodeError:
                    content = resp_body
                    data = {"raw": resp_body}
                
                metrics = UsageMetrics(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    latency_ms=latency * 1000
                )
                
                return ProviderResponse(
                    provider="http",
                    model="custom",
                    content=str(content),
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
