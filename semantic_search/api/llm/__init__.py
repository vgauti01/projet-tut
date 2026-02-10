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

def get_llm_service() -> LLMService:
    """ 
    Factory qui retourne le meilleur service de langage disponible.
    Actuellement, il n'y a qu'une implémentation locale, mais cette fonction peut être étendue à l'avenir pour inclure d'autres services de langage (par exemple, des services basés sur le cloud).
    """
    from config import LLM_MODEL_PATH
    service = LocalLLMService(LLM_MODEL_PATH)
    # Si le service local est disponible (par exemple, si le modèle est chargé correctement), on le retourne.
    if service.is_available():
        return service
    # Fallback: retourner quand même le service local. 
    return service
