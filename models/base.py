from abc import ABC, abstractmethod

class BaseAIModel(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:

        pass
