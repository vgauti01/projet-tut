
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import httpx
import numpy as np
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
from config import (
    MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME, TOP_K, EMBED_MODEL, RERANK_MODEL,
    CORS_ORIGINS, RRF_K, MIN_SCORE_THRESHOLD, SEARCH_MULTIPLIER
)
from utils import format_answer, extract_terms, reciprocal_rank_fusion
from health import health_checker
from resilience import (
    meili_circuit_breaker,
    qdrant_circuit_breaker,
    retry_async,
    CircuitBreakerOpenError
)
from metrics import (
    SearchMetrics,
    ModelMetrics,
    update_circuit_breaker_metrics,
    update_dependency_health,
    estimate_model_memory
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Assistant Hybride (BM25 + Vector)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Load model once at startup
print(f"Loading embedding model {EMBED_MODEL}...")
model = SentenceTransformer(EMBED_MODEL)
# Estimate: MiniLM-L12 is ~120MB, L6 is ~80MB
estimate_model_memory(EMBED_MODEL, 120_000_000)

print(f"Loading rerank model {RERANK_MODEL}...")
cross_encoder = CrossEncoder(RERANK_MODEL)
estimate_model_memory(RERANK_MODEL, 80_000_000)

qdrant_client = QdrantClient(url=QDRANT_URL)

# Mark models as loaded
health_checker.mark_models_loaded()
print("✅ All models loaded successfully")

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Question de l'utilisateur")
    limit: int | None = Field(None, ge=1, le=100, description="Nombre de résultats (1-100)")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La requête ne peut pas être vide ou composée uniquement d'espaces")
        return v

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


async def search_meilisearch(query: str, limit: int) -> List[Dict]:
    """
    Search Meilisearch with circuit breaker and retry logic.
    Returns empty list on failure for graceful degradation.
    """
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    payload = {
        "q": query,
        "limit": limit * SEARCH_MULTIPLIER,
        "attributesToRetrieve": ["id", "content", "title", "path", "page", "chunk_id"],
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
        # Use circuit breaker and retry
        result = await meili_circuit_breaker.call_async(
            retry_async,
            _do_search,
            max_attempts=2,
            initial_delay=0.5,
            exceptions=(httpx.HTTPError,)
        )
        return result.get("hits", [])
    except CircuitBreakerOpenError as e:
        logger.warning(f"Meilisearch circuit breaker open: {e}. Degrading to vector-only search.")
        return []
    except Exception as e:
        logger.error(f"Meilisearch search failed: {e}. Degrading to vector-only search.")
        return []


async def search_qdrant(query: str, limit: int) -> List[Dict]:
    """
    Search Qdrant with circuit breaker and retry logic.
    Returns empty list on failure for graceful degradation.
    """
    async def _do_search():
        with ModelMetrics("embed"):
            query_vector = model.encode(query).tolist()
        return qdrant_client.search(
            collection_name=INDEX_NAME,
            query_vector=query_vector,
            limit=limit * SEARCH_MULTIPLIER
        )

    try:
        # Use circuit breaker and retry
        qdrant_res = await qdrant_circuit_breaker.call_async(
            retry_async,
            _do_search,
            max_attempts=2,
            initial_delay=0.5,
            exceptions=(Exception,)
        )

        # Convert to dict format
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

@app.get("/health")
async def health():
    """Legacy health check - kept for backward compatibility."""
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    """
    Liveness probe - Is the service alive?
    Returns 200 if the service is running.
    """
    return await health_checker.liveness_check()


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe - Is the service ready to accept traffic?
    Returns 200 if ready, 503 if not ready.
    """
    result = await health_checker.readiness_check()
    if result["status"] == "ready":
        return result
    else:
        raise HTTPException(status_code=503, detail=result)


@app.get("/health/deep")
async def health_deep():
    """
    Deep health check - Detailed status of all components.
    Includes dependency checks and system metrics.
    """
    return await health_checker.deep_health_check()


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/ask")
async def ask(req: AskRequest):
    q = req.query  # Already validated and stripped by Pydantic
    limit = req.limit or TOP_K

    with SearchMetrics(q) as search_metrics:
        # 1. Search both engines in parallel with graceful degradation
        logger.info(f"Processing query: '{q}' (limit={limit})")

        # Execute searches in parallel
        import asyncio

        # Track Meilisearch search time
        meili_start = time.time()
        meili_task = asyncio.create_task(search_meilisearch(q, limit))

        # Track Qdrant search time
        qdrant_start = time.time()
        qdrant_task = asyncio.create_task(search_qdrant(q, limit))

        meili_hits, vector_hits = await asyncio.gather(meili_task, qdrant_task)

        # Record search times
        search_metrics.record_stage("meili", time.time() - meili_start)
        search_metrics.record_stage("qdrant", time.time() - qdrant_start)

        # Check if both searches failed
        if not meili_hits and not vector_hits:
            logger.error("Both search engines failed or returned no results")
            raise HTTPException(
                status_code=503,
                detail="Both search engines are unavailable. Please try again later."
            )

        # Determine search mode and log
        if not meili_hits and vector_hits:
            search_mode = "qdrant_only"
            logger.warning(f"Operating in degraded mode: vector-only (Meilisearch unavailable)")
        elif meili_hits and not vector_hits:
            search_mode = "meili_only"
            logger.warning(f"Operating in degraded mode: keyword-only (Qdrant unavailable)")
        else:
            search_mode = "hybrid"
            logger.info(f"Hybrid mode: found {len(meili_hits)} BM25 hits, {len(vector_hits)} vector hits")

        search_metrics.set_mode(search_mode)

        # 3. Reciprocal Rank Fusion (RRF) - Fusion intelligente des résultats
        rrf_start = time.time()
        candidates_pool = reciprocal_rank_fusion(
            meili_hits=meili_hits,
            vector_hits=vector_hits,
            k=RRF_K,
            limit=50  # Large pool for re-ranking
        )
        search_metrics.record_stage("rrf", time.time() - rrf_start)

        # 4. Re-ranking avec Cross-Encoder (The Judge)
        rerank_inputs = []
        docs_map = {}

        for i, (doc, rrf_score) in enumerate(candidates_pool):
            content = doc.get("content", "")
            docs_map[i] = doc
            rerank_inputs.append((q, content))

        if rerank_inputs:
            try:
                logger.info(f"Re-ranking {len(rerank_inputs)} candidates with cross-encoder")
                rerank_start = time.time()

                with ModelMetrics("rerank"):
                    scores = cross_encoder.predict(rerank_inputs)

                search_metrics.record_stage("rerank", time.time() - rerank_start)

                # Associer scores et docs
                ranked_results = []
                for i, score in enumerate(scores):
                    normalized_score = float(sigmoid(score))
                    ranked_results.append((docs_map[i], normalized_score))

                # Trier par score normalisé décroissant
                ranked_results.sort(key=lambda x: x[1], reverse=True)

                # Garder le top K final
                final_results = ranked_results[:limit]
                logger.info(f"Re-ranking successful, returning top {len(final_results)} results")

            except Exception as e:
                # Fallback: si le re-ranking échoue, utiliser les scores RRF
                logger.error(f"Re-ranking failed: {e}. Falling back to RRF scores.")
                final_results = candidates_pool[:limit]
        else:
            final_results = []

        # Track results count
        search_metrics.set_results_count(len(final_results))

        # 5. Extraction des termes et formatage de la réponse
        terms = extract_terms(q)
        answer = format_answer(q, final_results, terms)

        # Logging requests and results
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": q,
            "mode": search_mode,
            "results_count": len(final_results),
            "sources": answer.get("sources", [])
        }
        with open("requests.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        return answer
