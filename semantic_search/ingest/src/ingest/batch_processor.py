"""Traitement par batch des documents pour l'ingestion."""

import re
import hashlib
import logging
import requests
from pathlib import Path
from typing import Iterator, List, Dict, Any
from tqdm import tqdm
from qdrant_client.http import models

from .settings import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_MAX_TOKENS, EMBED_MODEL, MEILI_URL, INDEX_NAME, QDRANT_URL
from .text_utils import chunk_text, clean_pdf_artifacts
from .extractors import get_extractor
from .services.embedding_service import EmbeddingService
from .services.index_service import get_qdrant_client

logger = logging.getLogger(__name__)

# Singleton lazy pour le HybridChunker
_hybrid_chunker = None


def _get_hybrid_chunker():
    """Retourne un singleton HybridChunker configuré avec le tokenizer du modèle d'embedding."""
    global _hybrid_chunker
    if _hybrid_chunker is None:
        from docling.chunking import HybridChunker
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)
        _hybrid_chunker = HybridChunker(
            tokenizer=tokenizer,
            max_tokens=CHUNK_MAX_TOKENS,
            merge_peers=True,
        )
        logger.info(f"HybridChunker initialisé (max_tokens={CHUNK_MAX_TOKENS}, modèle={EMBED_MODEL})")
    return _hybrid_chunker


def _chunk_with_hybrid_chunker(
    docling_document: Any,
    title: str,
    file_path: Path,
    source_type: str,
) -> Iterator[Dict[str, Any]]:
    """
    Chunke un DoclingDocument avec le HybridChunker structure-aware.

    Utilise chunker.contextualize() pour enrichir chaque chunk avec les headings parents.
    Fallback vers chunk_text() si le chunker échoue.
    """
    try:
        chunker = _get_hybrid_chunker()
        chunks = list(chunker.chunk(docling_document))

        if not chunks:
            logger.warning(f"HybridChunker n'a produit aucun chunk pour {file_path}, fallback vers chunk_text")
            yield from _fallback_chunk_text(docling_document.export_to_markdown(), title, file_path, source_type)
            return

        clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', file_path.name)
        path_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]

        for idx, chunk in enumerate(chunks):
            # Texte enrichi avec headings parents via contextualize()
            contextualized_text = chunker.contextualize(chunk)
            content = f"Document: {title}\n\n{contextualized_text}"

            # Extraction des headings depuis les métadonnées du chunk
            headings = []
            if hasattr(chunk, 'meta') and hasattr(chunk.meta, 'headings'):
                headings = list(chunk.meta.headings) if chunk.meta.headings else []

            doc_id = f"{clean_filename}_{path_hash}_1_{idx}"

            yield {
                "id": doc_id,
                "title": title,
                "path": str(file_path),
                "page": 1,
                "chunk_id": idx,
                "content": content,
                "source_type": source_type,
                "headings": headings,
            }

    except Exception as e:
        logger.error(f"HybridChunker a échoué pour {file_path}: {e}", exc_info=True)
        logger.info(f"Fallback vers chunk_text() pour {file_path}")
        markdown = docling_document.export_to_markdown()
        yield from _fallback_chunk_text(markdown, title, file_path, source_type)


def _fallback_chunk_text(
    text: str,
    title: str,
    file_path: Path,
    source_type: str,
) -> Iterator[Dict[str, Any]]:
    """Fallback: chunke du texte brut avec chunk_text()."""
    clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', file_path.name)
    path_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]

    for idx, chunk in enumerate(chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
        doc_id = f"{clean_filename}_{path_hash}_1_{idx}"
        yield {
            "id": doc_id,
            "title": title,
            "path": str(file_path),
            "page": 1,
            "chunk_id": idx,
            "content": chunk,
            "source_type": source_type,
            "headings": [],
        }


def extract_documents(files: List[Path], docs_dir: Path) -> Iterator[Dict[str, Any]]:
    """
    Générateur qui extrait et chunke les documents un par un.
    Évite de charger tous les documents en mémoire en utilisant un yield.

    Args:
        files: Liste des fichiers à traiter
        docs_dir: Répertoire racine des documents

    Yields:
        Dictionnaire contenant les métadonnées et le contenu d'un chunk
    """
    for file_path in tqdm(files, desc="Extraction", unit="fichier"):
        extractor = get_extractor(file_path)
        if extractor is None:
            logger.warning(f"Pas d'extracteur pour {file_path}")
            continue

        title = file_path.stem

        try:
            for page in extractor.extract(file_path):
                # Vérifie que la page contient du texte non vide
                if not page.text.strip():
                    continue

                source_type = page.metadata.get("source_type", "unknown")

                # Chemin HybridChunker : si le DoclingDocument est disponible
                if page.docling_document is not None:
                    yield from _chunk_with_hybrid_chunker(
                        page.docling_document, title, file_path, source_type
                    )
                else:
                    # Chemin fallback : clean + chunk_text()
                    extraction_method = page.metadata.get("extraction_method", "")
                    if extraction_method.endswith("_fallback"):
                        cleaned_text = clean_pdf_artifacts(page.text)
                    else:
                        cleaned_text = page.text

                    if not cleaned_text.strip():
                        continue

                    # Parcourt les chunks de texte extraits de la page
                    for idx, chunk in enumerate(chunk_text(cleaned_text, CHUNK_SIZE, CHUNK_OVERLAP)):
                        # Génère un ID unique et stable basé sur hash pour éviter les collisions
                        clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', file_path.name)
                        # Ajout du hash du chemin complet pour garantir l'unicité
                        path_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
                        doc_id = f"{clean_filename}_{path_hash}_{page.page_number}_{idx}"

                        yield {
                            "id": doc_id,
                            "title": title,
                            "path": str(file_path),
                            "page": page.page_number,
                            "chunk_id": idx,
                            "content": chunk,
                            "source_type": source_type,
                            "headings": [],
                        }

        except Exception as e:
            logger.error(f"Erreur extraction {file_path}: {e}", exc_info=True)
            continue


def process_batch(
    batch_docs: List[Dict[str, Any]],
    embedding_service: EmbeddingService,
    meili_headers: Dict[str, str]
) -> tuple[int, int, int, int]:
    """
    Traite un batch de documents : génération embeddings + indexation.

    Args:
        batch_docs: Liste des documents du batch
        embedding_service: Service pour générer les embeddings
        meili_headers: Headers pour Meilisearch

    Returns:
        Tuple (meili_success, meili_failed, qdrant_success, qdrant_failed)
    """
    if not batch_docs:
        return 0, 0, 0, 0

    meili_success = 0
    meili_failed = 0
    qdrant_success = 0
    qdrant_failed = 0

    # Génération des embeddings pour le batch (encoding asymétrique document)
    try:
        contents = [doc["content"] for doc in batch_docs]
        embeddings = embedding_service.encode_documents(contents, show_progress=False)
    except Exception as e:
        logger.error(f"Erreur génération embeddings pour batch: {e}", exc_info=True)
        return 0, len(batch_docs), 0, len(batch_docs)

    # Indexation Meilisearch
    try:
        r = requests.post(
            f"{MEILI_URL}/indexes/{INDEX_NAME}/documents",
            headers=meili_headers,
            json=batch_docs,
            timeout=30
        )
        r.raise_for_status()
        meili_success = len(batch_docs)
    except requests.RequestException as e:
        meili_failed = len(batch_docs)
        logger.error(f"Erreur indexation Meilisearch: {e}")

    # Indexation Qdrant
    try:
        with get_qdrant_client(QDRANT_URL) as qdrant_client:
            points = []
            for i, doc in enumerate(batch_docs):
                # Hash 64 bits pour éviter les collisions (birthday paradox à ~65K chunks avec 32 bits)
                point_id = int(hashlib.md5(doc["id"].encode()).hexdigest()[:16], 16)
                points.append(models.PointStruct(
                    id=point_id,
                    vector=embeddings[i].tolist(),
                    payload=doc
                ))

            qdrant_client.upsert(
                collection_name=INDEX_NAME,
                points=points
            )
            qdrant_success = len(points)

    except Exception as e:
        qdrant_failed = len(batch_docs)
        logger.error(f"Erreur indexation Qdrant: {e}")

    return meili_success, meili_failed, qdrant_success, qdrant_failed
