from typing import Dict, Any
from .provider import BaseProvider, ProviderConfig, ProviderError, ProviderErrorType
from .mock import MockAIModel
from .gemini import GeminiProvider
from .venice import VeniceProvider

def get_provider(config: ProviderConfig, mock_responses: Dict[str, str] = None) -> BaseProvider:
    provider_name = config.provider_name.lower()
    
    if provider_name == "mock":
        return MockAIModel(config=config, predefined_responses=mock_responses)
    elif provider_name == "gemini":
        return GeminiProvider(config=config)
    elif provider_name == "venice":
        return VeniceProvider(config=config)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
