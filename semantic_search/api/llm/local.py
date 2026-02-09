import os
import asyncio
import logging
import queue
import threading
from pathlib import Path
from typing import AsyncIterator, Dict, Any, List, Optional

from .base import LLMService, ChatMessage, LLMConfig

logger = logging.getLogger(__name__)


class LocalLLMService(LLMService):
    """LLM service using llama-cpp-python for local GGUF model inference."""

    def __init__(self, model_path: str = "", config: Optional[LLMConfig] = None):
        self._model = None
        self._model_path = model_path
        self._lock = asyncio.Lock()

        if config is None:
            from config import (
                LLM_N_CTX, LLM_N_THREADS, LLM_GPU_LAYERS,
                LLM_TEMPERATURE, LLM_MAX_TOKENS
            )
            self._config = LLMConfig(
                model_path=model_path,
                n_ctx=LLM_N_CTX,
                n_threads=LLM_N_THREADS if LLM_N_THREADS > 0 else (os.cpu_count() or 4) // 2,
                n_gpu_layers=LLM_GPU_LAYERS,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
        else:
            self._config = config

        self._load_model()

    def _load_model(self):
        if not self._model_path or not Path(self._model_path).is_file():
            if self._model_path:
                logger.warning(f"LLM model file not found: {self._model_path}")
            else:
                logger.info("LLM_MODEL_PATH not set, LLM features disabled")
            return

        try:
            from llama_cpp import Llama
            logger.info(f"Loading LLM model from {self._model_path}...")
            self._model = Llama(
                model_path=self._model_path,
                n_ctx=self._config.n_ctx,
                n_threads=self._config.n_threads,
                n_gpu_layers=self._config.n_gpu_layers,
                verbose=False,
            )
            logger.info("LLM model loaded successfully")
        except ImportError:
            logger.warning("llama-cpp-python not installed, LLM features disabled")
        except Exception as e:
            logger.error(f"Failed to load LLM model: {e}")

    def is_available(self) -> bool:
        return self._model is not None

    async def generate(self, messages: List[ChatMessage]) -> str:
        if not self.is_available():
            raise RuntimeError("LLM model not available")

        formatted = [{"role": m.role, "content": m.content} for m in messages]

        async with self._lock:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_generate, formatted)
        return result

    def _sync_generate(self, messages: List[dict]) -> str:
        response = self._model.create_chat_completion(
            messages=messages,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return response["choices"][0]["message"]["content"]

    async def generate_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        if not self.is_available():
            raise RuntimeError("LLM model not available")

        formatted = [{"role": m.role, "content": m.content} for m in messages]
        token_queue: queue.Queue = queue.Queue()
        error_holder: List[Optional[Exception]] = [None]

        def _run_generation():
            try:
                for chunk in self._model.create_chat_completion(
                    messages=formatted,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens,
                    stream=True,
                ):
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        token_queue.put(content)
                token_queue.put(None)  # sentinel
            except Exception as e:
                error_holder[0] = e
                token_queue.put(None)

        async with self._lock:
            thread = threading.Thread(target=_run_generation, daemon=True)
            thread.start()

            while True:
                # Poll the queue without blocking the event loop
                while True:
                    try:
                        token = token_queue.get_nowait()
                        break
                    except queue.Empty:
                        await asyncio.sleep(0.01)

                if token is None:
                    if error_holder[0]:
                        raise error_holder[0]
                    break
                yield token

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "backend": "llama-cpp-python",
            "model_path": self._model_path,
            "available": self.is_available(),
            "n_ctx": self._config.n_ctx,
            "n_threads": self._config.n_threads,
            "n_gpu_layers": self._config.n_gpu_layers,
        }
