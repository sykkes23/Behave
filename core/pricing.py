from dataclasses import dataclass
from typing import Dict, Optional
from models.provider import UsageMetrics

@dataclass
class PricingModel:
    provider: str
    model: str
    input_cost_per_million: float
    output_cost_per_million: float

class PricingEngine:
    VERSION = "2026-08-01"


    _registry: Dict[str, PricingModel] = {
        "gemini:gemini-1.5-flash": PricingModel("gemini", "gemini-1.5-flash", 0.075, 0.30),
        "venice:venice-default": PricingModel("venice", "venice-default", 0.40, 0.40),

    }

    @classmethod
    def get_pricing(cls, provider: str, model: str) -> Optional[PricingModel]:
        key = f"{provider}:{model}"
        return cls._registry.get(key)

    @classmethod
    def calculate_cost(cls, provider: str, model: str, usage: UsageMetrics) -> Optional[float]:
        if usage.input_tokens is None or usage.output_tokens is None:
            return None

        pricing = cls.get_pricing(provider, model)
        if not pricing:
            return None

        input_cost = (usage.input_tokens / 1_000_000.0) * pricing.input_cost_per_million
        output_cost = (usage.output_tokens / 1_000_000.0) * pricing.output_cost_per_million

        return input_cost + output_cost

@dataclass
class UsageRecord:
    role: str
    provider: str
    model: str
    usage: UsageMetrics
    cost_usd: Optional[float] = None

    @classmethod
    def from_response(cls, role: str, provider: str, model: str, usage: UsageMetrics) -> 'UsageRecord':
        cost = PricingEngine.calculate_cost(provider, model, usage)
        return cls(
            role=role,
            provider=provider,
            model=model,
            usage=usage,
            cost_usd=cost
        )
