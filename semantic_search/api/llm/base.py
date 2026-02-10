""" Fichier de base pour les services de langage (LLM). Définit les interfaces et les structures de données communes. """

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Any, List, Optional


@dataclass
class ChatMessage:
    """ 
    Représente un message dans une conversation de chat.
    """
    # indique qui a envoyé le message (par exemple, "system" pour les instructions du système, "user" pour les messages de l'utilisateur, et "assistant" pour les réponses générées par le modèle).
    role: str
    # Le contenu du message (texte).
    content: str


@dataclass
class LLMConfig:
    """
    Configuration pour les services de langage (LLM).
    """
    # Chemin vers le modèle à utiliser (par exemple, un chemin local vers un modèle LLaMA).
    model_path: str = "" 
    # Nombre de tokens à utiliser pour le contexte (input + output).
    n_ctx: int = 2048
    # Nombre de threads à utiliser pour l'inférence (0 = auto).
    n_threads: int = 0  # 0 = auto
    # Nombre de couches du modèle à utiliser sur le GPU (0 = auto, -1 = CPU).
    n_gpu_layers: int = 0
    # Température pour la génération de texte (plus élevé = plus créatif, plus bas = plus déterministe).
    temperature: float = 0.7
    # Nombre de tokens à générer dans la réponse.
    max_tokens: int = 512


class LLMService(ABC):
    """Interface abstraite pour les services de langage (LLM)."""

    @abstractmethod
    def is_available(self) -> bool:
        """Indique si le service de langage est disponible (par exemple, si le modèle est chargé correctement)."""
        ...

    @abstractmethod
    async def generate(self, messages: List[ChatMessage]) -> str:
        """Génère une réponse basée sur une liste de messages de chat."""
        ...

    @abstractmethod
    async def generate_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        """Génère une réponse en streaming basée sur une liste de messages de chat."""
        ...

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le modèle utilisé (par exemple, nom, version, etc.)."""
        ...
