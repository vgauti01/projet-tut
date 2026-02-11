"""
Points de terminaison de vérification de santé (health check) pour surveiller l'état du service et de ses dépendances.
"""
import time
from typing import Dict, Any
from datetime import datetime
import httpx
from qdrant_client import AsyncQdrantClient
from .config import MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME


class HealthChecker:
    """ Gère les vérifications de santé du service et de ses dépendances (Meilisearch, Qdrant, LLM). """

    def __init__(self):
        """Initialise le HealthChecker avec un timestamp de démarrage et des indicateurs de chargement des modèles."""
        self.startup_time = time.time()
        self.models_loaded = False
        self.embed_model_status = "not_loaded"
        self.rerank_model_status = "not_loaded"

    def mark_models_loaded(self):
        """Marque que les modèles d'IA ont été chargés avec succès."""
        self.models_loaded = True
        self.embed_model_status = "loaded"
        self.rerank_model_status = "loaded"

    def get_uptime(self) -> float:
        """Obtenir le temps de fonctionnement du service en secondes."""
        return time.time() - self.startup_time

    async def check_meilisearch(self) -> Dict[str, Any]:
        """Vérifie la connectivité et le statut de Meilisearch."""
        start = time.time()
        try:
            headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{MEILI_URL}/health", headers=headers)
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    # Vérifie si l'index existe
                    index_response = await client.get(
                        f"{MEILI_URL}/indexes/{INDEX_NAME}",
                        headers=headers
                    )
                    index_exists = index_response.status_code == 200

                    return {
                        "status": "up",
                        "latency_ms": round(latency_ms, 2),
                        "index_exists": index_exists,
                        "index_name": INDEX_NAME
                    }
                else:
                    return {
                        "status": "degraded",
                        "latency_ms": round(latency_ms, 2),
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return {
                "status": "down",
                "latency_ms": round(latency_ms, 2),
                "error": str(e)
            }

    async def check_qdrant(self) -> Dict[str, Any]:
        """Vérifie la connectivité et le statut de Qdrant."""
        start = time.time()
        client = AsyncQdrantClient(url=QDRANT_URL, timeout=5.0)
        try:
            # Vérifie les collections
            collections = await client.get_collections()
            latency_ms = (time.time() - start) * 1000

            collection_exists = any(c.name == INDEX_NAME for c in collections.collections)

            collection_info = None
            if collection_exists:
                coll = await client.get_collection(INDEX_NAME)
                collection_info = {
                    "vectors_count": getattr(coll, "vectors_count", coll.points_count),
                    "points_count": coll.points_count
                }

            return {
                "status": "up",
                "latency_ms": round(latency_ms, 2),
                "collection_exists": collection_exists,
                "collection_name": INDEX_NAME,
                "collection_info": collection_info
            }
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return {
                "status": "down",
                "latency_ms": round(latency_ms, 2),
                "error": str(e)
            }
        finally:
            await client.close()

    def check_llm(self) -> Dict[str, Any]:
        """Vérifie la disponibilité du LLM et les informations sur le modèle."""
        try:
            from .llm import get_llm_service
            llm = get_llm_service()
            info = llm.get_model_info()
            return {
                "status": "up" if llm.is_available() else "disabled",
                **info
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_models_status(self) -> Dict[str, str]:
        """Obtenir le statut de chargement des modèles d'embeddings et de reranking."""
        return {
            "embed_model": self.embed_model_status,
            "rerank_model": self.rerank_model_status
        }

    async def liveness_check(self) -> Dict[str, Any]:
        """
        Liveness probe - Est-ce que le service est vivant ?
        Utilisé par les orchestrateurs pour redémarrer le service s'il ne répond pas.
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def readiness_check(self) -> Dict[str, Any]:
        """
        Readiness probe - Le service est-il prêt à accepter du trafic ?
        Utilisé par les équilibreurs de charge pour savoir si le trafic doit être dirigé ici.
        """
        issues = []

        # Vérifie que les modèles sont chargés - si ce n'est pas le cas, le service n'est pas prêt même s'il est vivant.
        if not self.models_loaded:
            issues.append("Models not loaded yet")

        # Vérifie les dépendances externes (Meilisearch et Qdrant). Si l'une d'elles est injoignable, le service n'est pas prêt.
        meili_status = await self.check_meilisearch()
        qdrant_status = await self.check_qdrant()

        if meili_status["status"] == "down":
            issues.append(f"Meilisearch unreachable: {meili_status.get('error', 'unknown')}")

        if qdrant_status["status"] == "down":
            issues.append(f"Qdrant unreachable: {qdrant_status.get('error', 'unknown')}")

        # Le service est considéré comme prêt uniquement s'il n'y a aucun problème détecté.
        is_ready = len(issues) == 0

        # Retourne un résumé de l'état de préparation du service, y compris les statuts des dépendances et les problèmes rencontrés.
        return {
            "status": "ready" if is_ready else "not_ready",
            "models_loaded": self.models_loaded,
            "meilisearch": meili_status["status"],
            "qdrant": qdrant_status["status"],
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def deep_health_check(self) -> Dict[str, Any]:
        """
        Deep health check - Statut détaillé de tous les composants.
        Utilisé pour la surveillance et le débogage.
        """
        meili_status = await self.check_meilisearch()
        qdrant_status = await self.check_qdrant()

        # Détermine le statut global du service en fonction des statuts de Meilisearch, Qdrant et du chargement des modèles.
        overall_status = "healthy"
        if meili_status["status"] == "down" or qdrant_status["status"] == "down":
            overall_status = "unhealthy"
        elif meili_status["status"] == "degraded" or qdrant_status["status"] == "degraded":
            overall_status = "degraded"
        elif not self.models_loaded:
            overall_status = "starting"

        llm_status = self.check_llm()

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": round(self.get_uptime(), 2),
            "models": self.get_models_status(),
            "dependencies": {
                "meilisearch": meili_status,
                "qdrant": qdrant_status
            },
            "llm": llm_status,
            "service_info": {
                "version": "1.0.0",
                "environment": "production"
            }
        }


# Instanciation du HealthChecker qui sera utilisé pour les endpoints de santé de l'API.
health_checker = HealthChecker()
