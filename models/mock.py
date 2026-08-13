from .base import BaseAIModel

class MockAIModel(BaseAIModel):
    def __init__(self, predefined_responses=None):
        """
        predefined_responses: dict mapping prompt substrings to responses.
        If a prompt contains a key, it returns the value.
        """
        self.predefined_responses = predefined_responses or {}

    def generate_response(self, prompt: str) -> str:
        for key, response in self.predefined_responses.items():
            if key.lower() in prompt.lower():
                return response
        
        return "I am a mock response. I need more information to diagnose the issue."
