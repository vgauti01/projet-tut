"""
Prometheus metrics for monitoring API performance and health.
"""
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

# Request metrics
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_duration_seconds',
    'API request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# Search-specific metrics
SEARCH_COUNT = Counter(
    'search_requests_total',
    'Total number of search requests',
    ['mode']  # hybrid, meili_only, qdrant_only
)

SEARCH_LATENCY = Histogram(
    'search_duration_seconds',
    'Search operation latency by stage',
    ['stage'],  # meili, qdrant, rrf, rerank, total
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

SEARCH_RESULTS = Histogram(
    'search_results_count',
    'Number of results returned per search',
    buckets=(0, 1, 2, 3, 5, 10, 20, 50, 100)
)

# Model metrics
MODEL_INFERENCE_LATENCY = Histogram(
    'model_inference_duration_seconds',
    'Model inference latency',
    ['model_type'],  # embed, rerank
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

MODEL_MEMORY_USAGE = Gauge(
    'model_memory_bytes',
    'Estimated model memory usage in bytes',
    ['model_name']
)

# Error metrics
ERROR_COUNT = Counter(
    'api_errors_total',
    'Total number of errors',
    ['error_type', 'endpoint']
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'circuit_breaker_failures_total',
    'Total number of circuit breaker failures',
    ['service']
)

# Dependency health metrics
DEPENDENCY_UP = Gauge(
    'dependency_up',
    'Dependency health status (1=up, 0=down)',
    ['service']
)

DEPENDENCY_LATENCY = Gauge(
    'dependency_latency_milliseconds',
    'Dependency response latency',
    ['service']
)

# Application info
APP_INFO = Info('app_info', 'Application information')
APP_INFO.info({
    'version': '1.0.0',
    'name': 'semantic-search-api',
    'description': 'Hybrid RAG search system'
})


def track_request_metrics(endpoint: str):
    """
    Decorator to track request metrics for API endpoints.

    Usage:
        @track_request_metrics("/ask")
        async def ask(req: AskRequest):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()
                raise
            finally:
                duration = time.time() - start_time
                REQUEST_LATENCY.labels(method="POST", endpoint=endpoint).observe(duration)
                REQUEST_COUNT.labels(method="POST", endpoint=endpoint, status=status).inc()

        return wrapper
    return decorator


class SearchMetrics:
    """Context manager for tracking search metrics."""

    def __init__(self, query: str):
        self.query = query
        self.start_time = time.time()
        self.stage_times = {}
        self.mode = "unknown"
        self.results_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        total_duration = time.time() - self.start_time
        SEARCH_LATENCY.labels(stage="total").observe(total_duration)
        SEARCH_COUNT.labels(mode=self.mode).inc()
        SEARCH_RESULTS.observe(self.results_count)

        logger.info(
            f"Search completed: mode={self.mode}, results={self.results_count}, "
            f"duration={total_duration:.3f}s"
        )

        return False  # Don't suppress exceptions

    def record_stage(self, stage: str, duration: float):
        """Record duration for a specific search stage."""
        self.stage_times[stage] = duration
        SEARCH_LATENCY.labels(stage=stage).observe(duration)
        logger.debug(f"Search stage '{stage}' completed in {duration:.3f}s")

    def set_mode(self, mode: str):
        """Set the search mode (hybrid, meili_only, qdrant_only)."""
        self.mode = mode

    def set_results_count(self, count: int):
        """Set the number of results returned."""
        self.results_count = count


class ModelMetrics:
    """Context manager for tracking model inference metrics."""

    def __init__(self, model_type: str):
        self.model_type = model_type
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            MODEL_INFERENCE_LATENCY.labels(model_type=self.model_type).observe(duration)
        return False


def update_circuit_breaker_metrics(service: str, state: str, failure: bool = False):
    """
    Update circuit breaker metrics.

    Args:
        service: Service name (meilisearch, qdrant)
        state: Circuit breaker state (closed, open, half_open)
        failure: Whether this update is due to a failure
    """
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state_map.get(state, 0))

    if failure:
        CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()


def update_dependency_health(service: str, is_up: bool, latency_ms: float = 0):
    """
    Update dependency health metrics.

    Args:
        service: Service name (meilisearch, qdrant)
        is_up: Whether the service is up
        latency_ms: Response latency in milliseconds
    """
    DEPENDENCY_UP.labels(service=service).set(1 if is_up else 0)
    if is_up and latency_ms > 0:
        DEPENDENCY_LATENCY.labels(service=service).set(latency_ms)


def estimate_model_memory(model_name: str, size_bytes: int):
    """
    Record estimated model memory usage.

    Args:
        model_name: Name of the model
        size_bytes: Estimated memory usage in bytes
    """
    MODEL_MEMORY_USAGE.labels(model_name=model_name).set(size_bytes)
