"""
Module de recherche pour l'API de recherche sémantique.
Ce module gère les interactions avec Meilisearch et Qdrant, applique les stratégies de recherche et de fusion, 
et prépare les réponses formatées pour les utilisateurs.
"""
import logging
import asyncio
import time
from typing import List, Dict, Tuple

import numpy as np
import httpx
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import AsyncQdrantClient
from .config import (
    MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME,
    EMBED_MODEL, RERANK_MODEL, SEARCH_MULTIPLIER, RRF_K, TOP_K, MIN_SCORE_THRESHOLD
)
from .resilience import (
    meili_circuit_breaker,
    qdrant_circuit_breaker,
    retry_async,
    CircuitBreakerOpenError
)
from .metrics import ModelMetrics, SearchMetrics, estimate_model_memory
from .utils import reciprocal_rank_fusion
from .stopwords import normalize_query

# Configuration du logging.
logger = logging.getLogger(__name__)

# Chargement des modèles d'embeddings et de reranking au démarrage de l'application, avec estimation de la mémoire utilisée.
# Utilise HF_CACHE_DIR si défini pour charger depuis les modèles pré-téléchargés
import os
cache_dir = os.getenv("HF_CACHE_DIR")
print(f"Chargement du modèle d'embeddings {EMBED_MODEL}...")
print(f"Cache directory: {cache_dir or 'default (~/.cache/huggingface)'}")
embed_model = SentenceTransformer(EMBED_MODEL, cache_folder=cache_dir)
estimate_model_memory(EMBED_MODEL, 120_000_000)

print(f"Chargement du modèle de reranking {RERANK_MODEL}...")
cross_encoder = CrossEncoder(RERANK_MODEL, cache_folder=cache_dir)
estimate_model_memory(RERANK_MODEL, 80_000_000)

qdrant_client = AsyncQdrantClient(url=QDRANT_URL)

print("Tous les modèles ont été chargés avec succès")

def sigmoid(x):
    """
    Fonction sigmoïde pour normaliser les scores de similarité.
    Cette fonction est utilisée pour transformer les scores de similarité en une échelle de 0 à 1, ce qui facilite la fusion des résultats provenant de différentes sources (BM25 et vectorielle).
    """
    return 1 / (1 + np.exp(-x))


async def search_meilisearch(query: str, limit: int) -> List[Dict]:
    """Recherche dans Meilisearch avec gestion du circuit breaker et logique de retry."""
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}

    # Normalise la requête en supprimant les stop words et la ponctuation
    normalized_query = normalize_query(query)

    # Prépare la charge utile pour la requête de recherche, en spécifiant les attributs à récupérer et à surligner,
    # ainsi que le nombre de résultats à retourner (multiplié par un facteur pour compenser la fusion ultérieure).
    logger.debug(f"Requête normalisée pour Meilisearch: '{normalized_query}'")
    payload = {
        "q": normalized_query,
        "limit": limit * SEARCH_MULTIPLIER,
        "attributesToRetrieve": ["id", "content", "title", "path", "page", "chunk_id", "source_type", "headings"],
        "attributesToHighlight": ["content"]
    }

    async def _do_search():
        """Effectue la recherche dans Meilisearch en envoyant une requête POST à l'API de Meilisearch avec la charge utile préparée."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
                headers=headers,
                json=payload
            )
            # Si la requête échoue, une exception est levée pour déclencher la logique de retry et de circuit breaker.
            r.raise_for_status()
            # Retourne les résultats de la recherche (hits) extraits de la réponse JSON de Meilisearch.
            return r.json()

    try:
        # Exécution de la recherche via un "Circuit Breaker" pour protéger le système.
        # Si Meilisearch échoue trop souvent, le circuit s'ouvre et les appels sont bloqués pour éviter d'aggraver la panne.
        result = await meili_circuit_breaker.call_async(
            # On enveloppe l'appel avec une logique de "retry" (tentatives multiples) en cas d'erreur HTTP.
            retry_async, _do_search, max_attempts=2, initial_delay=0.5, exceptions=(httpx.HTTPError,)
        )
        return result.get("hits", [])
    except CircuitBreakerOpenError as e:
        # Mode dégradé : si Meilisearch est hors service, on continue la recherche sans lui (vector-only).
        logger.warning(f"Circuit breaker Meilisearch ouvert : {e}. Passage en mode recherche vectorielle uniquement.")
        return []
    except Exception as e:
        # Sécurité : on capture toute erreur réseau pour garantir que l'API renvoie toujours une réponse (même partielle).
        logger.error(f"La recherche Meilisearch a échoué : {e}. Passage en mode recherche vectorielle uniquement.")
        return []


async def search_qdrant(query: str, limit: int) -> List[Dict]:
    """Recherche dans Qdrant avec gestion du circuit breaker et logique de retry."""

    async def _do_search():
        """Effectue la recherche dans Qdrant en encodant la requête et en interrogeant le client Qdrant."""
        with ModelMetrics("embed"):
            normalized_query = normalize_query(query)
            if hasattr(embed_model, 'encode_query'):
                query_vector = embed_model.encode_query(normalized_query).tolist()
            else:
                query_vector = embed_model.encode(normalized_query).tolist()
        
        # Utilisation de query_points car search est manquant dans les versions récentes du client (1.16+)
        res = await qdrant_client.query_points(
            collection_name=INDEX_NAME,
            query=query_vector,
            limit=limit * SEARCH_MULTIPLIER
        )
        return res.points

    try:
        # Exécution avec protection par Circuit Breaker et mécanisme de retry.
        qdrant_res = await qdrant_circuit_breaker.call_async(
            retry_async, _do_search, max_attempts=2, initial_delay=0.5, exceptions=(Exception,)
        )
        vector_hits = []
        # Transformation des résultats Qdrant pour correspondre au format attendu par le reste de la pipeline.
        for hit in qdrant_res:
            payload = hit.payload
            payload["_formatted"] = {"content": payload["content"]}
            vector_hits.append(payload)
        return vector_hits
    except CircuitBreakerOpenError as e:
        # En cas de panne de Qdrant, on bascule en mode dégradé (BM25 seul via Meilisearch).
        logger.warning(f"Circuit breaker Qdrant ouvert : {e}. Passage en mode recherche textuelle uniquement.")
        return []
    except Exception as e:
        # Gestion proactive des erreurs pour éviter un crash total de la requête utilisateur.
        logger.error(f"La recherche Qdrant a échoué : {e}. Passage en mode recherche textuelle uniquement.")
        return []


async def perform_hybrid_search(
    query: str,
    limit: int = TOP_K
) -> Tuple[List[Tuple[Dict, float]], str, Dict[str, float]]:
    """
    Exécute une recherche hybride complète (BM25 + Vectoriel + Reranking).

    Retourne:
        Tuple (final_results, search_mode, timings)
        final_results est une liste de tuples (document, score)
        timings contient les durées en ms de chaque étape
    """
    timings: Dict[str, float] = {}
    with SearchMetrics(query) as search_metrics:
        logger.info(f"Début de la recherche hybride pour: '{query}' (limit={limit})")

        # Lancement parallèle
        meili_start = time.time()
        meili_task = asyncio.create_task(search_meilisearch(query, limit))
        qdrant_start = time.time()
        qdrant_task = asyncio.create_task(search_qdrant(query, limit))

        meili_hits, vector_hits = await asyncio.gather(meili_task, qdrant_task)

        timings["meilisearch_ms"] = round((time.time() - meili_start) * 1000, 1)
        timings["qdrant_ms"] = round((time.time() - qdrant_start) * 1000, 1)
        search_metrics.record_stage("meili", time.time() - meili_start)
        search_metrics.record_stage("qdrant", time.time() - qdrant_start)

        if not meili_hits and not vector_hits:
            logger.error("Les deux moteurs de recherche ont échoué ou n'ont retourné aucun résultat")
            search_metrics.set_mode("failed")
            return [], "failed", timings

        if not meili_hits:
            search_mode = "qdrant_only"
            logger.warning("Mode dégradé : vectoriel uniquement (Meilisearch indisponible)")
        elif not vector_hits:
            search_mode = "meili_only"
            logger.warning("Mode dégradé : textuel uniquement (Qdrant indisponible)")
        else:
            search_mode = "hybrid"
            logger.info(f"Mode hybride : {len(meili_hits)} BM25, {len(vector_hits)} vectoriels")

        search_metrics.set_mode(search_mode)

        # RRF fusion
        rrf_start = time.time()
        candidates = reciprocal_rank_fusion(meili_hits, vector_hits, k=RRF_K, limit=50)
        timings["rrf_fusion_ms"] = round((time.time() - rrf_start) * 1000, 1)
        search_metrics.record_stage("rrf", time.time() - rrf_start)

        # Reranking avec Cross-encoder
        rerank_inputs = []
        docs_map = {}
        for i, (doc, _) in enumerate(candidates):
            docs_map[i] = doc
            rerank_inputs.append((query, doc.get("content", "")))

        final_results = []
        if rerank_inputs:
            try:
                logger.debug(f"Reranking de {len(rerank_inputs)} candidats")
                rerank_start = time.time()
                with ModelMetrics("rerank"):
                    scores = cross_encoder.predict(rerank_inputs)
                timings["reranking_ms"] = round((time.time() - rerank_start) * 1000, 1)
                search_metrics.record_stage("rerank", time.time() - rerank_start)

                ranked = []
                for i, score in enumerate(scores):
                    normalized_score = float(sigmoid(score))
                    # Filtrage par seuil de pertinence minimum
                    if normalized_score >= MIN_SCORE_THRESHOLD:
                        ranked.append((docs_map[i], normalized_score))

                ranked.sort(key=lambda x: x[1], reverse=True)
                final_results = ranked[:limit]

                if len(ranked) < len(scores):
                    filtered_count = len(scores) - len(ranked)
                    logger.info(f"{filtered_count} résultats filtrés (score < {MIN_SCORE_THRESHOLD})")
            except Exception as e:
                logger.error(f"Le reranking a échoué : {e}. Retour aux scores RRF.")
                final_results = candidates[:limit]

        search_metrics.set_results_count(len(final_results))
        return final_results, search_mode, timings
