
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import httpx
import numpy as np
import json
from datetime import datetime
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from config import (
    MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME, TOP_K, EMBED_MODEL,
    CORS_ORIGINS, RRF_K, MIN_SCORE_THRESHOLD, SEARCH_MULTIPLIER
)
from utils import format_answer, extract_terms, reciprocal_rank_fusion

app = FastAPI(title="Assistant Hybride (BM25 + Vector)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Load model once at startup
print(f"Loading model {EMBED_MODEL}...")
model = SentenceTransformer(EMBED_MODEL)
qdrant_client = QdrantClient(url=QDRANT_URL)

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
    return {"status": "ok"}

@app.post("/ask")
async def ask(req: AskRequest):
    q = req.query  # Already validated and stripped by Pydantic
    limit = req.limit or TOP_K
    
    # 1. Meilisearch (BM25) - Recherche par mots-clés
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    payload = {
        "q": q,
        "limit": limit * SEARCH_MULTIPLIER,  # Rechercher plus de résultats pour améliorer la fusion
        "attributesToRetrieve": ["id", "content","title","path","page","chunk_id"],
        "attributesToHighlight": ["content"]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
                                  headers=headers, json=payload)
            r.raise_for_status()
            meili_res = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Erreur de communication avec Meilisearch: {str(e)}")

    meili_hits = meili_res.get("hits", [])

    # 2. Qdrant (Vector) - Recherche sémantique
    try:
        query_vector = model.encode(q).tolist()
        qdrant_res = qdrant_client.search(
            collection_name=INDEX_NAME,
            query_vector=query_vector,
            limit=limit * SEARCH_MULTIPLIER  # Rechercher plus de résultats pour améliorer la fusion
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erreur de communication avec Qdrant: {str(e)}")
    
    vector_hits = []
    for hit in qdrant_res:
        payload = hit.payload
        # Mock highlighting for vector results
        payload["_formatted"] = {"content": payload["content"]}
        vector_hits.append(payload)

    # 3. Reciprocal Rank Fusion (RRF) - Fusion intelligente des résultats
    fused_results = reciprocal_rank_fusion(
        meili_hits=meili_hits,
        vector_hits=vector_hits,
        k=RRF_K,
        limit=limit * 2  # Obtenir plus de résultats pour pouvoir filtrer
    )

    # 4. Filtrage par score minimum pour éliminer les résultats peu pertinents
    filtered_results = [
        (doc, score) for doc, score in fused_results
        if score >= MIN_SCORE_THRESHOLD
    ][:limit]

    # 5. Extraction des termes et formatage de la réponse
    terms = extract_terms(q)
    answer = format_answer(q, filtered_results, terms)

    # Logging requests and results
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": q,
        "answer": answer.get("answer"),
        "sources": answer.get("sources", [])
    }
    with open("requests.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return answer
