"""Service de génération d'embeddings avec lazy loading."""

import os
import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service pour gérer le modèle d'embeddings avec lazy loading."""

    def __init__(self, model_name: str, cache_dir: str = None):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        logger.info(f"EmbeddingService initialisé (modèle: {model_name})")
        logger.info(f"Cache directory: {cache_dir or 'default (~/.cache/huggingface)'}")

    @property
    def model(self) -> Any:
        """Lazy loading du modèle - ne charge qu'à la première utilisation."""
        if self._model is None:
            logger.info(f"Chargement du modèle {self.model_name}...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, cache_folder=self.cache_dir)
            logger.info(f"Modèle chargé avec succès (dimension: {self._model.get_sentence_embedding_dimension()})")
        return self._model

    def get_embedding_dimension(self) -> int:
        """Retourne la dimension des vecteurs d'embeddings."""
        return self.model.get_sentence_embedding_dimension()

    def encode_batch(self, texts: List[str], show_progress: bool = False) -> Any:
        """Génère les embeddings pour un batch de textes."""
        return self.model.encode(texts, show_progress_bar=show_progress)


# Instance globale du service d'embeddings (lazy loading)
_embedding_service = None


def get_embedding_service(model_name: str = None, cache_dir: str = None) -> EmbeddingService:
    """
    Retourne l'instance globale du service d'embeddings.

    Args:
        model_name: Nom du modèle (utilisé seulement à la première initialisation)
        cache_dir: Répertoire de cache (utilisé seulement à la première initialisation)

    Returns:
        Instance du service d'embeddings
    """
    global _embedding_service
    if _embedding_service is None:
        if model_name is None:
            from ..settings import EMBED_MODEL
            model_name = EMBED_MODEL
        if cache_dir is None:
            cache_dir = os.getenv("HF_CACHE_DIR")
        _embedding_service = EmbeddingService(model_name, cache_dir)
    return _embedding_service
