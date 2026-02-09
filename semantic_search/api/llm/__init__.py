from .base import LLMService, LLMConfig, ChatMessage
from .local import LocalLLMService

__all__ = ["LLMService", "LLMConfig", "ChatMessage", "LocalLLMService", "get_llm_service"]


def get_llm_service() -> LLMService:
    """Factory: returns the best available LLM service."""
    from config import LLM_MODEL_PATH
    service = LocalLLMService(LLM_MODEL_PATH)
    if service.is_available():
        return service
    # Fallback: return the local service anyway (is_available will be False)
    return service
