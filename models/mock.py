import time
from typing import Dict
from .provider import BaseProvider, ProviderResponse, ProviderConfig

class MockAIModel(BaseProvider):
    def __init__(self, config: ProviderConfig, predefined_responses: Dict[str, str] = None):
        super().__init__(config)
        self.predefined_responses = predefined_responses or {}

    def generate_response(self, prompt: str) -> ProviderResponse:
        start_time = time.time()
        
        response_text = "I am a mock response. I need more information to diagnose the issue."
        for key, response in self.predefined_responses.items():
            if key.lower() in prompt.lower():
                response_text = response
                break
                
        latency = (time.time() - start_time) * 1000
        
        return ProviderResponse(
            provider="mock",
            model=self.config.model_name,
            content=response_text,
            input_tokens=10,
            output_tokens=len(response_text.split()),
            total_tokens=10 + len(response_text.split()),
            latency_ms=latency,
            model_version="mock-v1"
        )
