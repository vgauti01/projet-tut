from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Any, List, Optional


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMConfig:
    model_path: str = ""
    n_ctx: int = 2048
    n_threads: int = 0  # 0 = auto
    n_gpu_layers: int = 0
    temperature: float = 0.7
    max_tokens: int = 512


class LLMService(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    async def generate(self, messages: List[ChatMessage]) -> str:
        ...

    @abstractmethod
    async def generate_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        ...

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        ...
