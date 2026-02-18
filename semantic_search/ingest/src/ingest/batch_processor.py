"""Traitement par batch des documents pour l'ingestion."""

import re
import hashlib
import logging
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, List, Dict, Any
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models

from .settings import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_MAX_TOKENS, EMBED_MODEL, MEILI_URL, INDEX_NAME, QDRANT_URL, N_EXTRACTION_WORKERS, FILE_BATCH_SIZE
from .text_utils import chunk_text, clean_pdf_artifacts
from .extractors import get_extractor
from .services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# Singleton lazy pour le HybridChunker (thread-safe)
_hybrid_chunker = None
_hybrid_chunker_lock = threading.Lock()

# Lock pour la génération d'embeddings (PyTorch n'est pas thread-safe en inférence concurrente)
_embedding_lock = threading.Lock()


def _get_hybrid_chunker():
    """Retourne un singleton HybridChunker configuré avec le tokenizer du modèle d'embedding."""
    global _hybrid_chunker
    if _hybrid_chunker is None:
        with _hybrid_chunker_lock:
            if _hybrid_chunker is None:  # double-checked locking
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


def _extract_file_chunks(file_path: Path, docs_dir: Path) -> Iterator[Dict[str, Any]]:
    """
    Générateur qui extrait et chunke un seul fichier page par page.
    Ne charge jamais le fichier entier en RAM.
    """
    extractor = get_extractor(file_path)
    if extractor is None:
        logger.warning(f"Pas d'extracteur pour {file_path}")
        return

    title = file_path.stem

    try:
        for page in extractor.extract(file_path):
            if not page.text.strip():
                continue

            source_type = page.metadata.get("source_type", "unknown")

            if page.docling_document is not None:
                yield from _chunk_with_hybrid_chunker(
                    page.docling_document, title, file_path, source_type
                )
            else:
                extraction_method = page.metadata.get("extraction_method", "")
                cleaned_text = clean_pdf_artifacts(page.text) if extraction_method.endswith("_fallback") else page.text

                if not cleaned_text.strip():
                    continue

                clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', file_path.name)
                path_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]

                for idx, chunk in enumerate(chunk_text(cleaned_text, CHUNK_SIZE, CHUNK_OVERLAP)):
                    yield {
                        "id": f"{clean_filename}_{path_hash}_{page.page_number}_{idx}",
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


def _process_file(
    file_path: Path,
    docs_dir: Path,
    embedding_service: EmbeddingService,
    meili_headers: Dict[str, str],
    qdrant_client: QdrantClient,
) -> tuple[int, int, int, int, int]:
    """
    Parse et indexe un seul fichier par sous-batches au fil de la génération.
    Au plus FILE_BATCH_SIZE chunks en RAM à la fois, même pour les fichiers énormes.

    Returns:
        Tuple (extracted, meili_success, meili_failed, qdrant_success, qdrant_failed)
    """
    total_extracted = total_m_success = total_m_failed = total_q_success = total_q_failed = 0

    batch: List[Dict[str, Any]] = []
    for chunk in _extract_file_chunks(file_path, docs_dir):
        batch.append(chunk)
        if len(batch) >= FILE_BATCH_SIZE:
            m_s, m_f, q_s, q_f = process_batch(batch, embedding_service, meili_headers, qdrant_client)
            total_extracted += len(batch)
            total_m_success += m_s
            total_m_failed += m_f
            total_q_success += q_s
            total_q_failed += q_f
            batch = []

    if batch:
        m_s, m_f, q_s, q_f = process_batch(batch, embedding_service, meili_headers, qdrant_client)
        total_extracted += len(batch)
        total_m_success += m_s
        total_m_failed += m_f
        total_q_success += q_s
        total_q_failed += q_f

    return total_extracted, total_m_success, total_m_failed, total_q_success, total_q_failed


def process_files_parallel(
    files: List[Path],
    docs_dir: Path,
    embedding_service: EmbeddingService,
    meili_headers: Dict[str, str],
    qdrant_client: QdrantClient,
) -> tuple[int, int, int, int, int]:
    """
    Traite tous les fichiers en parallèle.
    Chaque worker parse et indexe immédiatement son fichier — pas d'accumulation en RAM.

    Returns:
        Tuple (total_extracted, meili_success, meili_failed, qdrant_success, qdrant_failed)
    """
    total_extracted = total_meili_success = total_meili_failed = 0
    total_qdrant_success = total_qdrant_failed = 0

    logger.info(f"Traitement avec {N_EXTRACTION_WORKERS} workers (parse + indexation par fichier)")

    with ThreadPoolExecutor(max_workers=N_EXTRACTION_WORKERS) as executor:
        futures = {
            executor.submit(
                _process_file, f, docs_dir, embedding_service, meili_headers, qdrant_client
            ): f
            for f in files
        }

        with tqdm(total=len(files), desc="Traitement", unit="fichier") as pbar:
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    extracted, m_s, m_f, q_s, q_f = future.result()
                    total_extracted += extracted
                    total_meili_success += m_s
                    total_meili_failed += m_f
                    total_qdrant_success += q_s
                    total_qdrant_failed += q_f
                    if extracted > 0:
                        logger.info(f"{file_path.name}: {extracted} chunks → Meili {m_s}, Qdrant {q_s}")
                except Exception as e:
                    logger.error(f"Erreur traitement {file_path}: {e}", exc_info=True)
                finally:
                    pbar.update(1)

    return total_extracted, total_meili_success, total_meili_failed, total_qdrant_success, total_qdrant_failed


def _index_meili(batch_docs: List[Dict[str, Any]], meili_headers: Dict[str, str]) -> int:
    """Indexe un batch dans Meilisearch. Retourne le nombre de docs indexés."""
    r = requests.post(
        f"{MEILI_URL}/indexes/{INDEX_NAME}/documents",
        headers=meili_headers,
        json=batch_docs,
        timeout=30,
    )
    r.raise_for_status()
    return len(batch_docs)


def _index_qdrant(batch_docs: List[Dict[str, Any]], embeddings, qdrant_client: QdrantClient) -> int:
    """Indexe un batch dans Qdrant. Retourne le nombre de points indexés."""
    points = [
        models.PointStruct(
            id=int(hashlib.md5(doc["id"].encode()).hexdigest()[:16], 16),
            vector=embeddings[i].tolist(),
            payload=doc,
        )
        for i, doc in enumerate(batch_docs)
    ]
    qdrant_client.upsert(collection_name=INDEX_NAME, points=points)
    return len(points)


def process_batch(
    batch_docs: List[Dict[str, Any]],
    embedding_service: EmbeddingService,
    meili_headers: Dict[str, str],
    qdrant_client: QdrantClient,
) -> tuple[int, int, int, int]:
    """
    Traite un batch de documents : génération embeddings + indexation parallèle.

    Args:
        batch_docs: Liste des documents du batch
        embedding_service: Service pour générer les embeddings
        meili_headers: Headers pour Meilisearch
        qdrant_client: Client Qdrant persistant (réutilisé entre batches)

    Returns:
        Tuple (meili_success, meili_failed, qdrant_success, qdrant_failed)
    """
    if not batch_docs:
        return 0, 0, 0, 0

    # Génération des embeddings pour le batch (encoding asymétrique document)
    # Lock nécessaire : PyTorch n'est pas sûr en inférence multi-thread concurrente
    try:
        contents = [doc["content"] for doc in batch_docs]
        with _embedding_lock:
            embeddings = embedding_service.encode_documents(contents, show_progress=False)
    except Exception as e:
        logger.error(f"Erreur génération embeddings pour batch: {e}", exc_info=True)
        return 0, len(batch_docs), 0, len(batch_docs)

    # Indexation Meilisearch + Qdrant en parallèle
    meili_success = meili_failed = qdrant_success = qdrant_failed = 0

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_meili = executor.submit(_index_meili, batch_docs, meili_headers)
        f_qdrant = executor.submit(_index_qdrant, batch_docs, embeddings, qdrant_client)

        try:
            meili_success = f_meili.result()
        except Exception as e:
            meili_failed = len(batch_docs)
            logger.error(f"Erreur indexation Meilisearch: {e}")

        try:
            qdrant_success = f_qdrant.result()
        except Exception as e:
            qdrant_failed = len(batch_docs)
            logger.error(f"Erreur indexation Qdrant: {e}")

    return meili_success, meili_failed, qdrant_success, qdrant_failed
