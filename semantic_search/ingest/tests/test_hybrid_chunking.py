"""Tests for HybridChunker integration and asymmetric encoding."""

import re
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingest.extractors.base import ExtractedPage
from ingest.services.embedding_service import EmbeddingService


class TestExtractDocumentsRouting:
    """Test le routing dans extract_documents() entre HybridChunker et chunk_text."""

    def test_docling_document_present_routes_to_hybrid_chunker(self):
        """Quand docling_document est présent, _chunk_with_hybrid_chunker est appelé."""
        from ingest.batch_processor import extract_documents

        fake_doc = MagicMock()
        fake_doc.export_to_markdown.return_value = "# Title\nSome content"

        page = ExtractedPage(
            page_number=1,
            text="# Title\nSome content",
            metadata={"source_type": "pdf", "extraction_method": "docling"},
            docling_document=fake_doc,
        )

        fake_extractor = MagicMock()
        fake_extractor.extract.return_value = iter([page])

        with patch("ingest.batch_processor.get_extractor", return_value=fake_extractor), \
             patch("ingest.batch_processor._chunk_with_hybrid_chunker") as mock_hybrid:
            mock_hybrid.return_value = iter([{
                "id": "test_1",
                "title": "test",
                "path": "test.pdf",
                "page": 1,
                "chunk_id": 0,
                "content": "chunk content",
                "source_type": "pdf",
                "headings": [],
            }])

            chunks = list(extract_documents([Path("test.pdf")], Path(".")))

            mock_hybrid.assert_called_once()
            assert len(chunks) == 1

    def test_docling_document_absent_routes_to_chunk_text(self):
        """Quand docling_document est None, le chemin fallback chunk_text est utilisé."""
        from ingest.batch_processor import extract_documents

        page = ExtractedPage(
            page_number=1,
            text="Some plain text content for testing the fallback path.",
            metadata={"source_type": "txt", "extraction_method": "txt"},
        )

        fake_extractor = MagicMock()
        fake_extractor.extract.return_value = iter([page])

        with patch("ingest.batch_processor.get_extractor", return_value=fake_extractor), \
             patch("ingest.batch_processor._chunk_with_hybrid_chunker") as mock_hybrid:

            chunks = list(extract_documents([Path("test.txt")], Path(".")))

            mock_hybrid.assert_not_called()
            assert len(chunks) >= 1
            assert chunks[0]["source_type"] == "txt"
            assert chunks[0]["headings"] == []


class TestChunkWithHybridChunker:
    """Test le format de sortie de _chunk_with_hybrid_chunker."""

    def test_output_format(self):
        """Les chunks produits ont les clés attendues."""
        from ingest.batch_processor import _chunk_with_hybrid_chunker

        # Mock du DoclingDocument
        fake_doc = MagicMock()

        # Mock du chunk retourné par le HybridChunker
        mock_chunk = MagicMock()
        mock_chunk.meta.headings = ["Chapter 1", "Section A"]

        # Mock du HybridChunker
        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk]
        mock_chunker.contextualize.return_value = "Chapter 1 > Section A\nSome contextualized text"

        with patch("ingest.batch_processor._get_hybrid_chunker", return_value=mock_chunker):
            chunks = list(_chunk_with_hybrid_chunker(
                fake_doc, "TestDoc", Path("test.pdf"), "pdf"
            ))

        assert len(chunks) == 1
        chunk = chunks[0]

        # Vérification des clés
        expected_keys = {"id", "title", "path", "page", "chunk_id", "content", "source_type", "headings"}
        assert set(chunk.keys()) == expected_keys

        # Vérification du contenu
        assert chunk["title"] == "TestDoc"
        assert chunk["content"].startswith("Document: TestDoc\n\n")
        assert chunk["source_type"] == "pdf"
        assert chunk["headings"] == ["Chapter 1", "Section A"]
        assert chunk["chunk_id"] == 0

    def test_fallback_on_chunker_failure(self):
        """Si le HybridChunker échoue, fallback vers chunk_text."""
        from ingest.batch_processor import _chunk_with_hybrid_chunker

        fake_doc = MagicMock()
        fake_doc.export_to_markdown.return_value = "Some markdown content for fallback testing."

        mock_chunker = MagicMock()
        mock_chunker.chunk.side_effect = RuntimeError("Chunker failed")

        with patch("ingest.batch_processor._get_hybrid_chunker", return_value=mock_chunker):
            chunks = list(_chunk_with_hybrid_chunker(
                fake_doc, "TestDoc", Path("test.pdf"), "pdf"
            ))

        assert len(chunks) >= 1
        # Le fallback produit des chunks sans headings
        assert chunks[0]["headings"] == []
        assert chunks[0]["source_type"] == "pdf"

    def test_fallback_on_empty_chunks(self):
        """Si le HybridChunker produit 0 chunks, fallback vers chunk_text."""
        from ingest.batch_processor import _chunk_with_hybrid_chunker

        fake_doc = MagicMock()
        fake_doc.export_to_markdown.return_value = "Content for fallback."

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = []

        with patch("ingest.batch_processor._get_hybrid_chunker", return_value=mock_chunker):
            chunks = list(_chunk_with_hybrid_chunker(
                fake_doc, "TestDoc", Path("test.pdf"), "pdf"
            ))

        assert len(chunks) >= 1
        assert chunks[0]["headings"] == []


class TestAsymmetricEncoding:
    """Test l'encoding asymétrique dans EmbeddingService."""

    def test_encode_documents_uses_encode_document_when_available(self):
        """encode_documents() délègue à model.encode_document() si disponible."""
        service = EmbeddingService("fake-model")
        mock_model = MagicMock()
        mock_model.encode_document.return_value = [[0.1, 0.2, 0.3]]
        service._model = mock_model

        result = service.encode_documents(["test text"])
        mock_model.encode_document.assert_called_once_with(["test text"], show_progress_bar=False)
        assert result == [[0.1, 0.2, 0.3]]

    def test_encode_documents_falls_back_to_encode(self):
        """encode_documents() utilise model.encode() si encode_document n'existe pas."""
        service = EmbeddingService("fake-model")
        mock_model = MagicMock(spec=["encode", "get_sentence_embedding_dimension"])
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        service._model = mock_model

        result = service.encode_documents(["test text"])
        mock_model.encode.assert_called_once_with(["test text"], show_progress_bar=False)
        assert result == [[0.1, 0.2, 0.3]]

    def test_encode_query_uses_encode_query_when_available(self):
        """encode_query() délègue à model.encode_query() si disponible."""
        service = EmbeddingService("fake-model")
        mock_model = MagicMock()
        mock_model.encode_query.return_value = [0.4, 0.5, 0.6]
        service._model = mock_model

        result = service.encode_query("test query")
        mock_model.encode_query.assert_called_once_with("test query")
        assert result == [0.4, 0.5, 0.6]

    def test_encode_query_falls_back_to_encode(self):
        """encode_query() utilise model.encode() si encode_query n'existe pas."""
        service = EmbeddingService("fake-model")
        mock_model = MagicMock(spec=["encode", "get_sentence_embedding_dimension"])
        mock_model.encode.return_value = [0.4, 0.5, 0.6]
        service._model = mock_model

        result = service.encode_query("test query")
        mock_model.encode.assert_called_once_with("test query")
        assert result == [0.4, 0.5, 0.6]

    def test_encode_batch_is_alias_for_encode_documents(self):
        """encode_batch() est un alias vers encode_documents()."""
        service = EmbeddingService("fake-model")
        mock_model = MagicMock()
        mock_model.encode_document.return_value = [[0.1, 0.2]]
        service._model = mock_model

        result = service.encode_batch(["text"])
        mock_model.encode_document.assert_called_once()
        assert result == [[0.1, 0.2]]
