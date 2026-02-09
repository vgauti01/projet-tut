"""
Search module: centralizes model loading and search functions.
Both app.py and chat.py import from here.
"""
import logging
import numpy as np
import httpx
from typing import List, Dict

from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from config import (
    MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME,
    EMBED_MODEL, RERANK_MODEL, SEARCH_MULTIPLIER
)
from resilience import (
    meili_circuit_breaker,
    qdrant_circuit_breaker,
    retry_async,
    CircuitBreakerOpenError
)
from metrics import ModelMetrics, estimate_model_memory

logger = logging.getLogger(__name__)

# Load models once at import time
print(f"Loading embedding model {EMBED_MODEL}...")
embed_model = SentenceTransformer(EMBED_MODEL)
estimate_model_memory(EMBED_MODEL, 120_000_000)

print(f"Loading rerank model {RERANK_MODEL}...")
cross_encoder = CrossEncoder(RERANK_MODEL)
estimate_model_memory(RERANK_MODEL, 80_000_000)

qdrant_client = QdrantClient(url=QDRANT_URL)

print("All models loaded successfully")


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


async def search_meilisearch(query: str, limit: int) -> List[Dict]:
    """Search Meilisearch with circuit breaker and retry logic."""
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    payload = {
        "q": query,
        "limit": limit * SEARCH_MULTIPLIER,
        "attributesToRetrieve": ["id", "content", "title", "path", "page", "chunk_id", "source_type"],
        "attributesToHighlight": ["content"]
    }

    async def _do_search():
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
                headers=headers,
                json=payload
            )
            r.raise_for_status()
            return r.json()

    try:
        result = await meili_circuit_breaker.call_async(
            retry_async, _do_search, max_attempts=2, initial_delay=0.5, exceptions=(httpx.HTTPError,)
        )
        return result.get("hits", [])
    except CircuitBreakerOpenError as e:
        logger.warning(f"Meilisearch circuit breaker open: {e}. Degrading to vector-only search.")
        return []
    except Exception as e:
        logger.error(f"Meilisearch search failed: {e}. Degrading to vector-only search.")
        return []


async def search_qdrant(query: str, limit: int) -> List[Dict]:
    """Search Qdrant with circuit breaker and retry logic."""

    async def _do_search():
        with ModelMetrics("embed"):
            query_vector = embed_model.encode(query).tolist()
        return qdrant_client.search(
            collection_name=INDEX_NAME,
            query_vector=query_vector,
            limit=limit * SEARCH_MULTIPLIER
        )

    try:
        qdrant_res = await qdrant_circuit_breaker.call_async(
            retry_async, _do_search, max_attempts=2, initial_delay=0.5, exceptions=(Exception,)
        )
        vector_hits = []
        for hit in qdrant_res:
            payload = hit.payload
            payload["_formatted"] = {"content": payload["content"]}
            vector_hits.append(payload)
        return vector_hits
    except CircuitBreakerOpenError as e:
        logger.warning(f"Qdrant circuit breaker open: {e}. Degrading to keyword-only search.")
        return []
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}. Degrading to keyword-only search.")
        return []
