from typing import AsyncIterator, Dict, Any, List

from .base import LLMService, ChatMessage


class OllamaLLMService(LLMService):
    """Stub for future Ollama integration."""

    def is_available(self) -> bool:
        return False

    async def generate(self, messages: List[ChatMessage]) -> str:
        raise NotImplementedError("Ollama backend not yet implemented")

    async def generate_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError("Ollama backend not yet implemented")
        yield  # make it a generator  # noqa

    def get_model_info(self) -> Dict[str, Any]:
        return {"backend": "ollama", "available": False}
