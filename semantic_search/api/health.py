"""
Health check endpoints for monitoring service status and dependencies.
"""
import time
from typing import Dict, Any
from datetime import datetime
import httpx
from qdrant_client import QdrantClient
from config import MEILI_URL, MEILI_MASTER_KEY, QDRANT_URL, INDEX_NAME


class HealthChecker:
    """Manages health checks for the application and its dependencies."""

    def __init__(self):
        self.startup_time = time.time()
        self.models_loaded = False
        self.embed_model_status = "not_loaded"
        self.rerank_model_status = "not_loaded"

    def mark_models_loaded(self):
        """Mark that AI models have been successfully loaded."""
        self.models_loaded = True
        self.embed_model_status = "loaded"
        self.rerank_model_status = "loaded"

    def get_uptime(self) -> float:
        """Get service uptime in seconds."""
        return time.time() - self.startup_time

    async def check_meilisearch(self) -> Dict[str, Any]:
        """Check Meilisearch connectivity and status."""
        start = time.time()
        try:
            headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{MEILI_URL}/health", headers=headers)
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    # Check if index exists
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
        """Check Qdrant connectivity and status."""
        start = time.time()
        try:
            client = QdrantClient(url=QDRANT_URL, timeout=5.0)

            # Check collections
            collections = client.get_collections()
            latency_ms = (time.time() - start) * 1000

            collection_exists = any(c.name == INDEX_NAME for c in collections.collections)

            collection_info = None
            if collection_exists:
                coll = client.get_collection(INDEX_NAME)
                collection_info = {
                    "vectors_count": coll.vectors_count,
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

    def check_llm(self) -> Dict[str, Any]:
        """Check LLM availability and model info."""
        try:
            from llm import get_llm_service
            llm = get_llm_service()
            info = llm.get_model_info()
            return {
                "status": "up" if llm.is_available() else "disabled",
                **info
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_models_status(self) -> Dict[str, str]:
        """Get AI models loading status."""
        return {
            "embed_model": self.embed_model_status,
            "rerank_model": self.rerank_model_status
        }

    async def liveness_check(self) -> Dict[str, Any]:
        """
        Liveness probe - Is the service alive?
        Used by Kubernetes/Docker to know if the service should be restarted.
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def readiness_check(self) -> Dict[str, Any]:
        """
        Readiness probe - Is the service ready to accept traffic?
        Used by load balancers to know if traffic should be routed here.
        """
        issues = []

        # Check if models are loaded
        if not self.models_loaded:
            issues.append("Models not loaded yet")

        # Quick check on dependencies (with timeout)
        meili_status = await self.check_meilisearch()
        qdrant_status = await self.check_qdrant()

        if meili_status["status"] == "down":
            issues.append(f"Meilisearch unreachable: {meili_status.get('error', 'unknown')}")

        if qdrant_status["status"] == "down":
            issues.append(f"Qdrant unreachable: {qdrant_status.get('error', 'unknown')}")

        is_ready = len(issues) == 0

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
        Deep health check - Detailed status of all components.
        Used for monitoring and debugging.
        """
        meili_status = await self.check_meilisearch()
        qdrant_status = await self.check_qdrant()

        # Determine overall health
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


# Global health checker instance
health_checker = HealthChecker()
