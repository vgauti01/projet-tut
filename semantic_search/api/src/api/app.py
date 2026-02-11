
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
    CORS_ORIGINS, TOP_K
)
from .search import (
    perform_hybrid_search
)
from .utils import format_answer, extract_terms
from .health import health_checker
from .metrics import SearchMetrics, ModelMetrics, track_request_metrics
from .chat import router as chat_router

# Configuration du logging pour l'application avec le timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Création de l'application FastAPI avec un titre descriptif.
app = FastAPI(title="Assistant RAG Hybride (BM25 + Vector)")

# Configuration du middleware CORS pour permettre les requêtes depuis les origines spécifiées dans la configuration
# Essentiel pour la communication entre le frontend et le backend de l'application.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# On marque les modèles comme chargés dans le HealthChecker après leur chargement réussi, ce qui affecte les réponses des endpoints de santé.
health_checker.mark_models_loaded()

# Inclut les routes de chat définies dans chat.py, qui gèrent les interactions de type conversationnel avec le service.
app.include_router(chat_router)

class AskRequest(BaseModel):
    """Modèle de requête pour l'endpoint /ask, avec validation des champs."""
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
    """Endpoint de vérification de vie (liveness) pour s'assurer que le service est opérationnel et répond aux requêtes de base."""
    return await health_checker.liveness_check()


@app.get("/health/ready")
async def health_ready():
    """Endpoint de vérification de préparation (readiness) pour s'assurer que le service est prêt à recevoir du trafic."""
    result = await health_checker.readiness_check()
    if result["status"] == "ready":
        return result
    else:
        raise HTTPException(status_code=503, detail=result)


@app.get("/health/deep")
async def health_deep():
    """Endpoint de vérification de santé approfondie (deep health check) pour obtenir un diagnostic détaillé de tous les composants du service."""
    return await health_checker.deep_health_check()


@app.get("/metrics")
async def metrics():
    """Endpoint pour exposer les métriques Prometheus, permettant la surveillance et l'observabilité du service."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/ask")
@track_request_metrics("/ask")
async def ask(req: AskRequest):
    """
    Endpoint principal pour traiter les requêtes de recherche.
    Gère la logique de recherche hybride, la fusion des résultats et le reranking.
    """
    q = req.query
    limit = req.limit or TOP_K

    # Exécution de la recherche hybride mutualisée
    final_results, search_mode = await perform_hybrid_search(q, limit)

    if search_mode == "failed":
        raise HTTPException(
            status_code=503,
            detail="Les moteurs de recherche sont indisponibles. Veuillez réessayer plus tard."
        )

    # Extraction des termes de la requête pour le surlignage dans les extraits de réponse.
    terms = extract_terms(q)
    # formatage de la réponse finale à retourner à l'utilisateur en utilisant les résultats rerankés.
    answer = format_answer(q, final_results, terms)

    # Enregistrement de la requête, du mode de recherche utilisé, du nombre de résultats et des sources dans un fichier de log.
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
    """Fonction pour démarrer le serveur Uvicorn, utilisée par le script de lancement dans pyproject.toml."""
    import uvicorn
    import os
    port = int(os.getenv("API_PORT", 8000))
    # Active le hot reload si DEV_MODE=true (utile en développement)
    reload = os.getenv("DEV_MODE", "false").lower() == "true"
    # Note: On utilise le module "api.app" pour l'import de l'application.
    # Ceci assume que le package est installé ou que le PYTHONPATH est correct.
    uvicorn.run("api.app:app", host="0.0.0.0", port=port, reload=reload)
