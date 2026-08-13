from abc import ABC, abstractmethod

class BaseAIModel(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """Generates a response from the AI model given a prompt."""
        pass
