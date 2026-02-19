"""Point d'entrée principal pour l'ingestion de documents."""

import logging
from pathlib import Path

from .settings import MEILI_MASTER_KEY, DOCS_DIR, QDRANT_URL
from .services import (
    get_embedding_service,
    ensure_meili_index,
    ensure_qdrant_collection,
    clear_meili_index,
    clear_qdrant_collection,
    get_qdrant_client,
)
from .batch_processor import process_files

# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def ingest():
    """Lance le processus d'ingestion des documents, incluant l'indexation dans Meilisearch et Qdrant."""

    # Étape 1: Vider les bases existantes pour une ingestion propre
    logger.info("=" * 60)
    logger.info("PHASE 1: Nettoyage des bases de données")
    logger.info("=" * 60)
    clear_meili_index()
    clear_qdrant_collection()

    # Étape 2: Créer les index/collections nécessaires dans Meilisearch et Qdrant
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 2: Création des index")
    logger.info("=" * 60)
    ensure_meili_index()
    ensure_qdrant_collection()

    # Prépare les services et headers
    meili_headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    embedding_service = get_embedding_service()

    # Étape 3: Collecte des fichiers
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 3: Collecte des fichiers")
    logger.info("=" * 60)

    docs_dir = Path(DOCS_DIR)

    # Collecte tous les fichiers de manière récursive
    files = [f for f in docs_dir.rglob("*") if f.is_file()]

    if not files:
        logger.warning(f"Aucun document trouvé dans {docs_dir.resolve()}")
        return

    logger.info(f"Documents trouvés: {len(files)}")

    # Étape 4: Extraction et indexation par fichier (parse + sauvegarde immédiate)
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 4: Extraction et indexation")
    logger.info("=" * 60)

    # Client Qdrant persistant pour toute l'ingestion (une seule connexion)
    with get_qdrant_client(QDRANT_URL) as qdrant_client:
        total_extracted, total_meili_success, total_meili_failed, total_qdrant_success, total_qdrant_failed = (
            process_files(files, docs_dir, embedding_service, meili_headers, qdrant_client)
        )

    # Résumé final
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ DE L'INGESTION")
    logger.info("=" * 60)
    logger.info(f"Total segments extraits: {total_extracted}")
    logger.info(f"Meilisearch: {total_meili_success} indexés, {total_meili_failed} échecs")
    logger.info(f"Qdrant: {total_qdrant_success} indexés, {total_qdrant_failed} échecs")

    if total_extracted > 0:
        success_rate_meili = (total_meili_success / total_extracted) * 100
        success_rate_qdrant = (total_qdrant_success / total_extracted) * 100
        logger.info(f"Taux de succès Meilisearch: {success_rate_meili:.1f}%")
        logger.info(f"Taux de succès Qdrant: {success_rate_qdrant:.1f}%")

    logger.info("=" * 60)


if __name__ == "__main__":
    """Point d'entrée principal pour l'ingestion des documents."""
    ingest()

