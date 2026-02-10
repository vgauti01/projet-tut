"""
Modèle de résilience.

Ce module implémente ces patterns:

1. Circuit Breaker (Coupe-circuit) : Évite d'écraser un service déjà en surcharge ou en panne.
2. Retry (Réessai) : Tente de récupérer une erreur transitoire (ex: micro-coupure réseau)
   avec un délai progressif (Exponential Backoff).
3. Graceful Degradation : Permet à l'application de continuer à fonctionner (en mode dégradé)
   même si un composant non critique échoue.
"""
import time
import asyncio
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
import logging

# Configure le logger pour ce module
logger = logging.getLogger(__name__)

# Type générique pour les fonctions décorées par le circuit breaker et le retry
T = TypeVar('T')

class CircuitBreaker:
    """
    Implémentation du pattern Circuit Breaker (Coupe-circuit).

    Le principe est calqué sur l'électricité : 
    - CLOSED (Fermé) : L'électricité passe. Le service fonctionne normalement.
    - OPEN (Ouvert) : Le circuit est coupé. On ne tente même pas l'appel pour ne pas perdre de temps.
    - HALF_OPEN (Semi-ouvert) : On laisse passer quelques appels de test pour voir si le service est revenu.
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
        """Initialise le coupe-circuit avec les paramètres de seuil d'échec, délai de récupération et limite d'appels en mode semi-ouvert."""
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = self.CLOSED
        self.half_open_calls = 0

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Exécute une fonction synchrone sous la protection du coupe-circuit."""

        # Si le circuit est OUVERT, on vérifie si le délai de récupération est passé
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                # Le délai est passé, on passe en mode test (HALF_OPEN)
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (tentative de récupération)")
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
            else:
                # Sinon on "fail-fast" : on rejette l'appel immédiatement sans essayer
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} est OUVERT. "
                    f"Nouvel essai possible dans {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
                )

        # En mode HALF_OPEN, on limite le nombre d'appels simultanés de test
        if self.state == self.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} est HALF_OPEN (limite d'appels de test atteinte)"
                )
            self.half_open_calls += 1

        try:
            # Appel effectif de la fonction
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            # En cas d'erreur, on enregistre l'échec pour potentiellement ouvrir le circuit
            self._on_failure()
            raise e

    async def call_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Exécute une fonction asynchrone sous la protection du coupe-circuit."""

        # Si le circuit est OUVERT, on vérifie si le délai de récupération est passé
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                # Le délai est passé, on passe en mode test (HALF_OPEN)
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (tentative de récupération)")
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
            else:
                # Sinon on "fail-fast"
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} est OUVERT. "
                    f"Nouvel essai possible dans {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
                )

        # En mode HALF_OPEN, on limite le nombre d'appels simultanés de test
        if self.state == self.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} est HALF_OPEN (limite d'appels de test atteinte)"
                )
            self.half_open_calls += 1

        try:
            # Appel effectif de la fonction asynchrone
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            # En cas d'erreur, on enregistre l'échec
            self._on_failure()
            raise e

    def _on_success(self):
        """Action à effectuer après un appel réussi."""
        if self.state == self.HALF_OPEN:
            # Si un appel de test réussit, on considère que le service est à nouveau sain
            logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED (service rétabli)")
        self.failure_count = 0
        self.state = self.CLOSED
        self.half_open_calls = 0

    def _on_failure(self):
        """Action à effectuer après un échec."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            # Si on échoue pendant le test, on rouvre le circuit immédiatement
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (échec du test)")
            self.state = self.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            # Si le seuil d'erreurs est atteint, on coupe le circuit
            logger.error(
                f"Circuit breaker {self.name}: CLOSED -> OPEN "
                f"({self.failure_count} échecs, seuil de {self.failure_threshold} atteint)"
            )
            self.state = self.OPEN

    def reset(self):
        """Réinitialise manuellement le coupe-circuit."""
        logger.info(f"Circuit breaker {self.name}: réinitialisé manuellement à CLOSED")
        self.failure_count = 0
        self.state = self.CLOSED
        self.half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    """Exception levée quand le circuit est ouvert pour éviter d'appeler un service en panne."""
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
    Réessaie une fonction asynchrone avec un délai exponentiel (Exponential Backoff).

    C'est utile pour les erreurs temporaires. On attend de plus en plus longtemps
    entre chaque essai pour laisser le temps au service cible de respirer.

    Args:
        func: La fonction asynchrone à appeler.
        max_attempts: Nombre maximum d'essais (ex: 3).
        backoff_factor: Multiplicateur de délai (2.0 = double le temps à chaque fois).
        initial_delay: Premier délai d'attente en secondes.
        max_delay: Délai maximum autorisé entre deux essais.
        exceptions: Les types d'erreurs qui déclenchent un réessai.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                logger.error(f"Fonction {func.__name__} a échoué après {max_attempts} essais: {e}")
                raise

            logger.warning(
                f"Fonction {func.__name__} a échoué (essai {attempt}/{max_attempts}): {e}. "
                f"Nouvel essai dans {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            # Augmentation exponentielle du délai
            delay = min(delay * backoff_factor, max_delay)

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
    Version synchrone du retry avec Exponential Backoff.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                logger.error(f"Fonction {func.__name__} a échoué après {max_attempts} essais: {e}")
                raise

            logger.warning(
                f"Fonction {func.__name__} a échoué (essai {attempt}/{max_attempts}): {e}. "
                f"Nouvel essai dans {delay:.1f}s..."
            )
            time.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    raise last_exception


# Instances globales de coupe-circuits pour les services externes
# On sépare les deux car si Meilisearch tombe, Qdrant peut encore fonctionner (et inversement)
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
