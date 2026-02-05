"""
Resilience patterns for robust error handling.
Includes retry logic, circuit breaker, and graceful degradation.
"""
import time
import asyncio
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is tripped, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = self.CLOSED
        self.half_open_calls = 0

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""

        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (testing recovery)")
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Will retry in {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
                )

        # Limit calls in HALF_OPEN state
        if self.state == self.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is HALF_OPEN (max test calls reached)"
                )
            self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    async def call_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""

        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (testing recovery)")
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Will retry in {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
                )

        # Limit calls in HALF_OPEN state
        if self.state == self.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is HALF_OPEN (max test calls reached)"
                )
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call."""
        if self.state == self.HALF_OPEN:
            logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED (recovery confirmed)")
        self.failure_count = 0
        self.state = self.CLOSED
        self.half_open_calls = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            # Failed during recovery test, go back to OPEN
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (recovery failed)")
            self.state = self.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            # Too many failures, trip the circuit
            logger.error(
                f"Circuit breaker {self.name}: CLOSED -> OPEN "
                f"({self.failure_count} failures reached threshold {self.failure_threshold})"
            )
            self.state = self.OPEN

    def reset(self):
        """Manually reset the circuit breaker."""
        logger.info(f"Circuit breaker {self.name}: manually reset to CLOSED")
        self.failure_count = 0
        self.state = self.CLOSED
        self.half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


async def retry_async(
    func: Callable,
    *args,
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                raise

            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    # Should never reach here, but just in case
    raise last_exception


def retry_sync(
    func: Callable,
    *args,
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry a synchronous function with exponential backoff.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                raise

            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    raise last_exception


# Global circuit breakers for external services
meili_circuit_breaker = CircuitBreaker(
    name="meilisearch",
    failure_threshold=5,
    recovery_timeout=60.0
)

qdrant_circuit_breaker = CircuitBreaker(
    name="qdrant",
    failure_threshold=5,
    recovery_timeout=60.0
)
