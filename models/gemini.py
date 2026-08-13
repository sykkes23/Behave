import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any

from .provider import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType, ProviderConfig

class GeminiProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        # Default model if not specified
        self.model = config.model_name if config.model_name and config.model_name != "unknown" else "gemini-1.5-flash"
        
    def generate_response(self, prompt: str, history: list = None) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(ProviderErrorType.AUTH_ERROR, "Gemini API key is missing.")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
            }
        }
        if self.config.top_p is not None:
            payload["generationConfig"]["topP"] = self.config.top_p
        if self.config.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = self.config.max_tokens

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
        req.add_header('Content-Type', 'application/json')
        
        start_time = time.time()
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                latency_ms = (time.time() - start_time) * 1000
                response_data = json.loads(response.read().decode('utf-8'))
                
                content = response_data['candidates'][0]['content']['parts'][0]['text']
                usage = response_data.get('usageMetadata', {})
                input_tokens = usage.get('promptTokenCount')
                output_tokens = usage.get('candidatesTokenCount')
                total_tokens = usage.get('totalTokenCount')
                
                model_version = response_data.get('modelVersion', "unknown")
                
                return ProviderResponse(
                    provider="gemini",
                    model=self.model,
                    model_version=model_version,
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms
                )
                
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
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
                raise ProviderError(ProviderErrorType.TIMEOUT, "Request to Gemini timed out.")
            raise ProviderError(ProviderErrorType.PROVIDER_ERROR, f"Network error: {str(e)}")
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN_PROVIDER_ERROR, f"Unexpected error: {str(e)}")
