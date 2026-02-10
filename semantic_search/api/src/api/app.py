
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import json
import logging
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Tuple

from .config import (
    CORS_ORIGINS, RRF_K, TOP_K
)
from .search import (
    embed_model, cross_encoder, search_meilisearch, search_qdrant, sigmoid
)
from .utils import format_answer, extract_terms, reciprocal_rank_fusion
from .health import health_checker
from .metrics import SearchMetrics, ModelMetrics
from .chat import router as chat_router

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

# Mark models as loaded (they are loaded at search.py import time)
health_checker.mark_models_loaded()

# Register chat router
app.include_router(chat_router)

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


@app.get("/health")
async def health():
    """Legacy health check - kept for backward compatibility."""
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    return await health_checker.liveness_check()


@app.get("/health/ready")
async def health_ready():
    result = await health_checker.readiness_check()
    if result["status"] == "ready":
        return result
    else:
        raise HTTPException(status_code=503, detail=result)


@app.get("/health/deep")
async def health_deep():
    return await health_checker.deep_health_check()


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/ask")
async def ask(req: AskRequest):
    q = req.query
    limit = req.limit or TOP_K

    with SearchMetrics(q) as search_metrics:
        logger.info(f"Processing query: '{q}' (limit={limit})")

        meili_start = time.time()
        meili_task = asyncio.create_task(search_meilisearch(q, limit))
        qdrant_start = time.time()
        qdrant_task = asyncio.create_task(search_qdrant(q, limit))

        meili_hits, vector_hits = await asyncio.gather(meili_task, qdrant_task)

        search_metrics.record_stage("meili", time.time() - meili_start)
        search_metrics.record_stage("qdrant", time.time() - qdrant_start)

        if not meili_hits and not vector_hits:
            logger.error("Both search engines failed or returned no results")
            raise HTTPException(
                status_code=503,
                detail="Both search engines are unavailable. Please try again later."
            )

        if not meili_hits and vector_hits:
            search_mode = "qdrant_only"
            logger.warning("Operating in degraded mode: vector-only (Meilisearch unavailable)")
        elif meili_hits and not vector_hits:
            search_mode = "meili_only"
            logger.warning("Operating in degraded mode: keyword-only (Qdrant unavailable)")
        else:
            search_mode = "hybrid"
            logger.info(f"Hybrid mode: found {len(meili_hits)} BM25 hits, {len(vector_hits)} vector hits")

        search_metrics.set_mode(search_mode)

        # RRF fusion
        rrf_start = time.time()
        candidates_pool = reciprocal_rank_fusion(
            meili_hits=meili_hits,
            vector_hits=vector_hits,
            k=RRF_K,
            limit=50
        )
        search_metrics.record_stage("rrf", time.time() - rrf_start)

        # Cross-encoder reranking
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

                ranked_results = []
                for i, score in enumerate(scores):
                    normalized_score = float(sigmoid(score))
                    ranked_results.append((docs_map[i], normalized_score))

                ranked_results.sort(key=lambda x: x[1], reverse=True)
                final_results = ranked_results[:limit]
                logger.info(f"Re-ranking successful, returning top {len(final_results)} results")

            except Exception as e:
                logger.error(f"Re-ranking failed: {e}. Falling back to RRF scores.")
                final_results = candidates_pool[:limit]
        else:
            final_results = []

        search_metrics.set_results_count(len(final_results))

        terms = extract_terms(q)
        answer = format_answer(q, final_results, terms)

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

def serve():
    import uvicorn
    import os
    port = int(os.getenv("API_PORT", 8000))
    # Note: On utilise le module "api.app" pour l'import de l'application.
    # Ceci assume que le package est installé ou que le PYTHONPATH est correct.
    uvicorn.run("api.app:app", host="0.0.0.0", port=port, reload=False)
