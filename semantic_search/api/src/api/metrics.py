"""
Métriques Prometheus pour surveiller les performances et la santé de l'API.
"""
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

# Métriques de requête
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Nombre total de requêtes API',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_duration_seconds',
    'Latence des requêtes API en secondes',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# Métriques spécifiques à la recherche
SEARCH_COUNT = Counter(
    'search_requests_total',
    'Nombre total de requêtes de recherche',
    ['mode']  # hybrid, meili_only, qdrant_only
)

SEARCH_LATENCY = Histogram(
    'search_duration_seconds',
    'Latence des opérations de recherche par étape',
    ['stage'],  # meili, qdrant, rrf, rerank, total
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

SEARCH_RESULTS = Histogram(
    'search_results_count',
    'Nombre de résultats retournés par recherche',
    buckets=(0, 1, 2, 3, 5, 10, 20, 50, 100)
)

# Métriques des modèles d'IA
MODEL_INFERENCE_LATENCY = Histogram(
    'model_inference_duration_seconds',
    'Latence d\'inférence des modèles',
    ['model_type'],  # embed, rerank
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

MODEL_MEMORY_USAGE = Gauge(
    'model_memory_bytes',
    'Utilisation estimée de la mémoire par le modèle en octets',
    ['model_name']
)

# Métriques d'erreur
ERROR_COUNT = Counter(
    'api_errors_total',
    'Nombre total d\'erreurs',
    ['error_type', 'endpoint']
)

# Métriques du circuit breaker
CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'État du circuit breaker (0=fermé, 1=ouvert, 2=semi-ouvert)',
    ['service']
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'circuit_breaker_failures_total',
    'Nombre total d\'échecs du circuit breaker',
    ['service']
)

# Métriques de santé des dépendances
DEPENDENCY_UP = Gauge(
    'dependency_up',
    'Statut de santé de la dépendance (1=en ligne, 0=hors ligne)',
    ['service']
)

DEPENDENCY_LATENCY = Gauge(
    'dependency_latency_milliseconds',
    'Latence de réponse de la dépendance',
    ['service']
)

# Chat & LLM
CHAT_REQUESTS_TOTAL = Counter(
    'chat_requests_total',
    'Nombre total de requêtes chat',
    ['path']  # "llm" | "fallback"
)

LLM_GENERATION_DURATION = Histogram(
    'llm_generation_duration_seconds',
    'Durée de génération LLM par phase',
    ['phase'],  # "time_to_first_token" | "total_generation"
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

LLM_TOKENS_TOTAL = Counter(
    'llm_tokens_generated_total',
    'Nombre total de tokens générés par le LLM'
)

CHAT_SEARCH_DURATION = Histogram(
    'chat_search_duration_seconds',
    'Durée de la recherche hybride dans le contexte chat',
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

CHAT_PIPELINE_DURATION = Histogram(
    'chat_pipeline_duration_seconds',
    'Durée totale du pipeline chat (recherche + génération)',
    ['path'],  # "llm" | "fallback"
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
)

# Informations sur l'application
APP_INFO = Info('app_info', 'Informations sur l\'application')
APP_INFO.info({
    'version': '1.0.0',
    'name': 'semantic-search-api',
    'description': 'Système de recherche RAG Hybride'
})


def track_request_metrics(endpoint: str):
    """
    Décorateur pour suivre les métriques des requêtes API.

    Usage:
        @track_request_metrics("/ask")
        async def ask(req: AskRequest):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Lance le chronomètre pour mesurer la durée de la requête, et initialise le statut à "success".
            start_time = time.time()
            status = "success"

            try:
                # Exécute la fonction de l'endpoint et capture le résultat.
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # En cas d'exception, on met à jour le statut à "error", on incrémente le compteur d'erreurs avec le type d'erreur et l'endpoint,
                # et on relance l'exception pour que la gestion des erreurs de FastAPI puisse s'en occuper.
                status = "error"
                error_type = type(e).__name__
                ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()
                raise
            finally:
                # À la fin de l'exécution (qu'elle soit réussie ou qu'elle ait échoué), on calcule la durée totale de la requête et on met à jour les métriques de latence et de comptage des requêtes en fonction du statut final.
                duration = time.time() - start_time
                REQUEST_LATENCY.labels(method="POST", endpoint=endpoint).observe(duration)
                REQUEST_COUNT.labels(method="POST", endpoint=endpoint, status=status).inc()

        return wrapper
    return decorator


class SearchMetrics:
    """
    Context manager pour suivre les métriques spécifiques aux opérations de recherche.
    Ce context manager permet de mesurer la latence de chaque étape du processus de recherche (Meilisearch, Qdrant, RRF, reranking),
    ainsi que le mode de recherche utilisé (hybrid, meili_only, qdrant_only) et le nombre de résultats retournés, afin d'avoir une visibilité complète sur les performances et les comportements de la recherche.
    """

    def __init__(self, query: str):
        """Initialise le context manager avec la requête de recherche."""
        self.query = query
        self.start_time = time.time()
        self.stage_times = {}
        self.mode = "unknown"
        self.results_count = 0

    def __enter__(self):
        """Démarre le chronomètre pour mesurer la durée totale de la recherche et retourne le context manager lui-même pour permettre l'enregistrement des différentes étapes et résultats pendant le processus de recherche."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """À la fin de la recherche, calcule la durée totale, enregistre les métriques de latence et de comptage des recherches, et logue les résultats pour une analyse ultérieure."""
        total_duration = time.time() - self.start_time
        SEARCH_LATENCY.labels(stage="total").observe(total_duration)
        SEARCH_COUNT.labels(mode=self.mode).inc()
        SEARCH_RESULTS.observe(self.results_count)

        logger.info(
            f"Recherche terminée : mode={self.mode}, résultats={self.results_count}, "
            f"durée={total_duration:.3f}s"
        )

        return False  # Don't suppress exceptions

    def record_stage(self, stage: str, duration: float):
        """Enregistre la durée d'une étape spécifique de la recherche."""
        self.stage_times[stage] = duration
        SEARCH_LATENCY.labels(stage=stage).observe(duration)
        logger.debug(f"Étape de recherche '{stage}' terminée en {duration:.3f}s")

    def set_mode(self, mode: str):
        """Définit le mode de recherche (hybrid, meili_only, qdrant_only)."""
        self.mode = mode

    def set_results_count(self, count: int):
        """Définit le nombre de résultats retournés."""
        self.results_count = count


class ModelMetrics:
    """Context manager pour suivre les métriques d'inférence du modèle."""

    def __init__(self, model_type: str):
        """Initialise le context manager avec le type de modèle (embed, rerank)."""
        self.model_type = model_type
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """À la fin de l'inférence, calcule la durée et enregistre la métrique correspondante."""
        if self.start_time:
            duration = time.time() - self.start_time
            MODEL_INFERENCE_LATENCY.labels(model_type=self.model_type).observe(duration)
        return False


class ChatMetrics:
    """
    Objet stateful pour suivre les métriques du pipeline chat.
    Pas un context manager car le générateur SSE est async et lazy.
    """

    def __init__(self):
        self.pipeline_start = time.time()
        self.path = "unknown"
        self._gen_start = None
        self._first_token_recorded = False
        self._token_count = 0

    def record_search_duration(self, duration: float):
        """Enregistre la durée de la recherche hybride dans le contexte chat."""
        CHAT_SEARCH_DURATION.observe(duration)

    def set_path(self, path: str):
        """Définit le chemin emprunté : 'llm' ou 'fallback'."""
        self.path = path

    def start_generation(self):
        """Marque le début de la génération LLM."""
        self._gen_start = time.time()

    def record_first_token(self):
        """Enregistre le temps jusqu'au premier token."""
        if not self._first_token_recorded and self._gen_start:
            ttft = time.time() - self._gen_start
            LLM_GENERATION_DURATION.labels(phase="time_to_first_token").observe(ttft)
            self._first_token_recorded = True

    def record_token(self):
        """Incrémente le compteur interne de tokens."""
        self._token_count += 1

    def finish_generation(self):
        """Enregistre la durée totale de génération et le nombre de tokens."""
        if self._gen_start:
            total = time.time() - self._gen_start
            LLM_GENERATION_DURATION.labels(phase="total_generation").observe(total)
            if self._token_count > 0:
                LLM_TOKENS_TOTAL.inc(self._token_count)

    def finish(self):
        """Enregistre la durée totale du pipeline et incrémente le compteur de requêtes."""
        duration = time.time() - self.pipeline_start
        CHAT_PIPELINE_DURATION.labels(path=self.path).observe(duration)
        CHAT_REQUESTS_TOTAL.labels(path=self.path).inc()


def update_circuit_breaker_metrics(service: str, state: str, failure: bool = False):
    """
    Met à jour les métriques du disjoncteur.

    Args:
        service: Nom du service (meilisearch, qdrant)
        state: État du disjoncteur (closed, open, half_open)
        failure: Indique si cette mise à jour est due à une défaillance
    """
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state_map.get(state, 0))

    if failure:
        CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()


def update_dependency_health(service: str, is_up: bool, latency_ms: float = 0):
    """
    Met à jour les métriques de santé des dépendances.

    Args:
        service: Nom du service (meilisearch, qdrant)
        is_up: Indique si le service est opérationnel
        latency_ms: Latence de réponse en millisecondes
    """
    DEPENDENCY_UP.labels(service=service).set(1 if is_up else 0)
    if is_up and latency_ms > 0:
        DEPENDENCY_LATENCY.labels(service=service).set(latency_ms)


def estimate_model_memory(model_name: str, size_bytes: int):
    """
    Enregistre l'utilisation estimée de la mémoire du modèle.

    Args:
        model_name: Nom du modèle
        size_bytes: Utilisation estimée de la mémoire en octets
    """
    MODEL_MEMORY_USAGE.labels(model_name=model_name).set(size_bytes)
