"""Services pour l'ingestion de documents."""

from .embedding_service import EmbeddingService, get_embedding_service
from .index_service import (
    ensure_meili_index,
    ensure_qdrant_collection,
    clear_meili_index,
    clear_qdrant_collection,
    get_qdrant_client,
)

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "ensure_meili_index",
    "ensure_qdrant_collection",
    "clear_meili_index",
    "clear_qdrant_collection",
    "get_qdrant_client",
]
