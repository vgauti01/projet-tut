from .base import LLMService, LLMConfig, ChatMessage
from .local import LocalLLMService

# En python, le champ __all__ est utilisé pour définir les symboles qui seront exportés lorsque quelqu'un importe le module avec "from module import *".
# Ici:
# - LLMService: la classe de base pour les services de langage.
# - LLMConfig: la classe de configuration pour les services de langage.
# - ChatMessage: la classe représentant un message de chat.
# - LocalLLMService: une implémentation locale du service de langage.
# - get_llm_service: une fonction de fabrique pour obtenir le meilleur service de langage disponible.
__all__ = ["LLMService", "LLMConfig", "ChatMessage", "LocalLLMService", "get_llm_service"]

# Cache global pour le service LLM afin d'éviter de recharger le modèle à chaque requête.
# Recharger un modèle de plusieurs Go est une opération lourde qui impacterait gravement les performances.
_llm_service_cache = None

def get_llm_service() -> LLMService:
    """ 
    Factory qui retourne le meilleur service de langage disponible.
    Utilise un cache interne pour retourner toujours la même instance (Singleton).
    """
    global _llm_service_cache
    if _llm_service_cache is not None:
        return _llm_service_cache

    from ..config import LLM_MODEL_PATH
    _llm_service_cache = LocalLLMService(LLM_MODEL_PATH)
    
    return _llm_service_cache
