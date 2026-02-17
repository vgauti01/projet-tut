"""Point d'entrée principal pour l'ingestion de documents."""

import os
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
from .batch_processor import extract_documents, process_batch

# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration des batches pour optimisation mémoire
BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "100"))


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

    # Étape 4: Extraction et indexation par batch (optimisation mémoire)
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 4: Extraction et indexation par batch")
    logger.info("=" * 60)
    logger.info(f"Taille des batches: {BATCH_SIZE} documents")

    # Compteurs globaux
    total_extracted = 0
    total_meili_success = 0
    total_meili_failed = 0
    total_qdrant_success = 0
    total_qdrant_failed = 0
    batch_num = 0

    # Client Qdrant persistant pour toute l'ingestion (une seule connexion)
    with get_qdrant_client(QDRANT_URL) as qdrant_client:
        # Traitement par batch avec générateur (économie mémoire)
        batch_docs = []
        for doc in extract_documents(files, docs_dir):
            batch_docs.append(doc)
            total_extracted += 1

            # Traitement du batch quand il atteint la taille limite
            if len(batch_docs) >= BATCH_SIZE:
                batch_num += 1
                logger.info(f"\nTraitement du batch {batch_num} ({len(batch_docs)} segments)...")

                # Génération embeddings + indexation
                m_success, m_failed, q_success, q_failed = process_batch(
                    batch_docs, embedding_service, meili_headers, qdrant_client
                )

                # Mise à jour des compteurs
                total_meili_success += m_success
                total_meili_failed += m_failed
                total_qdrant_success += q_success
                total_qdrant_failed += q_failed

                logger.info(f"Batch {batch_num} terminé - Meili: {m_success}/{len(batch_docs)}, Qdrant: {q_success}/{len(batch_docs)}")
                logger.info(f"Progression globale: {total_extracted} segments extraits, {total_meili_success} indexés")

                # Libération mémoire
                batch_docs = []

        # Traitement du dernier batch partiel
        if batch_docs:
            batch_num += 1
            logger.info(f"\nTraitement du dernier batch {batch_num} ({len(batch_docs)} segments)...")

            m_success, m_failed, q_success, q_failed = process_batch(
                batch_docs, embedding_service, meili_headers, qdrant_client
            )

            total_meili_success += m_success
            total_meili_failed += m_failed
            total_qdrant_success += q_success
            total_qdrant_failed += q_failed

            logger.info(f"Batch {batch_num} terminé - Meili: {m_success}/{len(batch_docs)}, Qdrant: {q_success}/{len(batch_docs)}")

    # Résumé final
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ DE L'INGESTION")
    logger.info("=" * 60)
    logger.info(f"Total segments extraits: {total_extracted}")
    logger.info(f"Nombre de batches traités: {batch_num}")
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

