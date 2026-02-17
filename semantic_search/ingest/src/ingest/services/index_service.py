"""Services de gestion des index Meilisearch et Qdrant."""

import logging
import requests
from contextlib import contextmanager
from qdrant_client import QdrantClient
from qdrant_client.http import models

from ..settings import MEILI_URL, MEILI_MASTER_KEY, INDEX_NAME, QDRANT_URL
from ..stopwords import FRENCH_STOP_WORDS
from .embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@contextmanager
def get_qdrant_client(url: str):
    """Context manager pour gérer proprement le client Qdrant."""
    client = QdrantClient(url=url)
    try:
        yield client
    finally:
        client.close()
        logger.debug("Fermeture du client Qdrant")


def clear_meili_index():
    """Vide complètement l'index Meilisearch avant de commencer l'ingestion."""
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}

    try:
        # Vérifie si l'index existe
        r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers, timeout=10)

        if r.status_code == 200:
            # L'index existe, on le supprime
            logger.info(f"Suppression de l'index Meilisearch '{INDEX_NAME}'...")
            r = requests.delete(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers, timeout=10)
            r.raise_for_status()
            logger.info("Index Meilisearch supprimé avec succès")
    except requests.RequestException as e:
        logger.error(f"Erreur lors de la suppression de l'index Meilisearch: {e}")
        raise


def ensure_meili_index():
    """Vérifie si l'index Meilisearch existe, et le crée avec les paramètres appropriés s'il n'existe pas."""
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}

    try:
        # Vérifie l'existence de l'index en envoyant une requête GET à l'API de Meilisearch
        r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers, timeout=10)

        # Si l'index n'existe pas (code 404), le crée en envoyant une requête POST avec les paramètres de l'index
        if r.status_code == 404:
            logger.info(f"Création de l'index Meilisearch '{INDEX_NAME}'...")
            r = requests.post(
                f"{MEILI_URL}/indexes",
                headers=headers,
                json={"uid": INDEX_NAME, "primaryKey": "id"},
                timeout=10
            )
            r.raise_for_status()
            logger.info("Index Meilisearch créé avec succès")

        # Configure les paramètres de l'index pour définir les attributs recherchables, filtrables et affichés
        # Note: Les stop words sont configurés mais s'appliquent uniquement lors de l'indexation
        # La normalisation des requêtes côté API (search.py) complète cette configuration
        logger.info("Configuration des paramètres de l'index Meilisearch...")
        r = requests.patch(
            f"{MEILI_URL}/indexes/{INDEX_NAME}/settings",
            headers=headers,
            json={
                "searchableAttributes": ["content", "title", "path"],
                "filterableAttributes": ["title", "path", "page", "source_type", "headings"],
                "displayedAttributes": ["content", "title", "path", "page", "chunk_id", "source_type", "headings"],
                "stopWords": FRENCH_STOP_WORDS
            },
            timeout=10
        )
        r.raise_for_status()
        logger.info("Paramètres Meilisearch configurés avec succès")

    except requests.RequestException as e:
        logger.error(f"Erreur lors de la configuration de l'index Meilisearch: {e}")
        raise


def clear_qdrant_collection():
    """Vide complètement la collection Qdrant avant de commencer l'ingestion."""
    with get_qdrant_client(QDRANT_URL) as client:
        try:
            collections = client.get_collections().collections
            exists = any(c.name == INDEX_NAME for c in collections)

            if exists:
                # La collection existe, on la supprime
                logger.info(f"Suppression de la collection Qdrant '{INDEX_NAME}'...")
                client.delete_collection(collection_name=INDEX_NAME)
                logger.info("Collection Qdrant supprimée avec succès")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la collection Qdrant: {e}")
            raise


def ensure_qdrant_collection():
    """Vérifie si la collection Qdrant existe, et la crée avec les paramètres appropriés si elle n'existe pas."""
    embedding_service = get_embedding_service()

    with get_qdrant_client(QDRANT_URL) as client:
        try:
            # Vérifie l'existence de la collection en récupérant la liste des collections existantes
            collections = client.get_collections().collections
            exists = any(c.name == INDEX_NAME for c in collections)

            # Récupère la taille des vecteurs d'embeddings à partir du service d'embeddings
            vector_size = embedding_service.get_embedding_dimension()

            # Si la collection n'existe pas, la crée en spécifiant le nom de la collection et la configuration des vecteurs
            if not exists:
                logger.info(f"Création de la collection Qdrant '{INDEX_NAME}'...")
                client.create_collection(
                    collection_name=INDEX_NAME,
                    vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
                )
                logger.info("Collection Qdrant créée avec succès")

        except Exception as e:
            logger.error(f"Erreur lors de la création de la collection Qdrant: {e}")
            raise
