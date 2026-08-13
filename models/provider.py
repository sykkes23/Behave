from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum
import time

class ProviderErrorType(str, Enum):
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"

class ProviderError(Exception):
    def __init__(self, error_type: ProviderErrorType, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"{error_type.value}: {message}")

@dataclass
class ProviderConfig:
    provider_name: str
    model_name: str = "unknown"
    temperature: float = 0.7
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    extra_settings: Dict[str, Any] = field(default_factory=dict)
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "api_key": self.api_key,
            **self.extra_settings
        }

@dataclass
class ProviderResponse:
    provider: str
    model: str
    content: str
    request_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[ProviderErrorType] = None
    model_version: str = "unknown"

class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def generate_response(self, prompt: str) -> ProviderResponse:
        """Generates a normalized response from the provider."""
        pass
