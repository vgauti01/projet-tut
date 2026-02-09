"""Tests for LLM service and prompt builder."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import ChatMessage, LLMConfig, LLMService
from llm.local import LocalLLMService
from llm.ollama import OllamaLLMService
from prompt import build_rag_prompt, SYSTEM_PROMPT


class TestChatMessage:
    def test_creation(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestLLMConfig:
    def test_defaults(self):
        config = LLMConfig()
        assert config.n_ctx == 2048
        assert config.n_threads == 0
        assert config.temperature == 0.7
        assert config.max_tokens == 512


class TestLocalLLMService:
    def test_unavailable_when_no_model(self):
        service = LocalLLMService(
            model_path="",
            config=LLMConfig()
        )
        assert service.is_available() is False

    def test_unavailable_when_file_missing(self):
        service = LocalLLMService(
            model_path="/nonexistent/model.gguf",
            config=LLMConfig()
        )
        assert service.is_available() is False

    def test_model_info(self):
        service = LocalLLMService(
            model_path="",
            config=LLMConfig()
        )
        info = service.get_model_info()
        assert info["backend"] == "llama-cpp-python"
        assert info["available"] is False


class TestOllamaLLMService:
    def test_unavailable(self):
        service = OllamaLLMService()
        assert service.is_available() is False

    def test_model_info(self):
        info = OllamaLLMService().get_model_info()
        assert info["backend"] == "ollama"
        assert info["available"] is False


class TestPromptBuilder:
    def test_build_basic(self):
        chunks = [
            ({"title": "Doc1", "page": 1, "content": "Some content", "source_type": "pdf"}, 0.95),
        ]
        messages = build_rag_prompt("What is X?", chunks)

        assert len(messages) == 2  # system + user
        assert messages[0].role == "system"
        assert messages[0].content == SYSTEM_PROMPT
        assert messages[1].role == "user"
        assert "What is X?" in messages[1].content
        assert "Some content" in messages[1].content
        assert "Doc1" in messages[1].content

    def test_with_history(self):
        chunks = [
            ({"title": "Doc", "page": 1, "content": "text", "source_type": "pdf"}, 0.5),
        ]
        history = [
            ChatMessage(role="user", content="prior q"),
            ChatMessage(role="assistant", content="prior a"),
        ]
        messages = build_rag_prompt("follow up?", chunks, history, max_history=5)

        assert len(messages) == 4  # system + 2 history + user
        assert messages[1].role == "user"
        assert messages[1].content == "prior q"
        assert messages[2].role == "assistant"
        assert messages[2].content == "prior a"

    def test_history_sliding_window(self):
        chunks = [({"title": "D", "page": 1, "content": "c", "source_type": "pdf"}, 0.5)]
        # 6 history messages = 3 pairs, max_history=1 should keep last 2
        history = [
            ChatMessage(role="user", content=f"q{i}")
            if i % 2 == 0 else ChatMessage(role="assistant", content=f"a{i}")
            for i in range(6)
        ]
        messages = build_rag_prompt("new?", chunks, history, max_history=1)
        # system + last 2 history msgs + user = 4
        assert len(messages) == 4

    def test_empty_chunks(self):
        messages = build_rag_prompt("test?", [])
        assert len(messages) == 2
        assert "test?" in messages[1].content
