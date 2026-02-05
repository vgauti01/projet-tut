"""
Tests for utils.py functions.
"""
import pytest
from utils import (
    highlight,
    extract_terms,
    reciprocal_rank_fusion,
    format_answer
)


class TestHighlight:
    """Tests for the highlight function."""

    def test_highlight_single_term(self):
        text = "This is a test document."
        terms = ["test"]
        result = highlight(text, terms)
        assert "**test**" in result

    def test_highlight_multiple_terms(self):
        text = "This is a test document with multiple terms."
        terms = ["test", "document"]
        result = highlight(text, terms)
        assert "**test**" in result
        assert "**document**" in result

    def test_highlight_case_insensitive(self):
        text = "This is a TEST document."
        terms = ["test"]
        result = highlight(text, terms)
        assert "**TEST**" in result

    def test_highlight_no_terms(self):
        text = "This is a test document."
        terms = []
        result = highlight(text, terms)
        assert result == text

    def test_highlight_word_boundaries(self):
        # Should not highlight "test" within "testing"
        text = "This is testing a test."
        terms = ["test"]
        result = highlight(text, terms)
        assert "testing" in result  # Not highlighted
        assert "**test**." in result  # Highlighted

    def test_highlight_with_special_chars(self):
        text = "The nRF24L01 module is great."
        terms = ["nRF24L01"]
        result = highlight(text, terms)
        assert "**nRF24L01**" in result


class TestExtractTerms:
    """Tests for the extract_terms function."""

    def test_extract_basic_terms(self):
        query = "How does the nRF24L01 work?"
        terms = extract_terms(query)
        assert "nRF24L01" in terms
        assert "work" in terms

    def test_filter_stop_words(self):
        query = "What is the best way to test?"
        terms = extract_terms(query)
        # Stop words should be filtered
        assert "the" not in terms
        assert "is" not in terms
        assert "to" not in terms
        # Significant terms should remain
        assert "best" in terms
        assert "way" in terms
        assert "test" in terms

    def test_filter_short_terms(self):
        query = "A B CD EFG test"
        terms = extract_terms(query)
        # Terms <= 2 chars should be filtered
        assert "A" not in terms
        assert "B" not in terms
        assert "CD" not in terms
        # Terms > 2 chars should remain
        assert "EFG" in terms
        assert "test" in terms

    def test_handle_special_characters(self):
        query = "Wi-Fi and Bluetooth connectivity"
        terms = extract_terms(query)
        assert "Wi-Fi" in terms
        assert "Bluetooth" in terms
        assert "connectivity" in terms


class TestReciprocalRankFusion:
    """Tests for the RRF algorithm."""

    def test_rrf_basic_fusion(self):
        meili_hits = [
            {"id": "doc1", "content": "test1"},
            {"id": "doc2", "content": "test2"}
        ]
        vector_hits = [
            {"id": "doc2", "content": "test2"},
            {"id": "doc3", "content": "test3"}
        ]

        result = reciprocal_rank_fusion(meili_hits, vector_hits, k=60, limit=10)

        # doc2 should be ranked higher (appears in both)
        assert len(result) == 3
        assert result[0][0]["id"] == "doc2"

    def test_rrf_empty_meili(self):
        meili_hits = []
        vector_hits = [
            {"id": "doc1", "content": "test1"}
        ]

        result = reciprocal_rank_fusion(meili_hits, vector_hits, k=60, limit=10)

        assert len(result) == 1
        assert result[0][0]["id"] == "doc1"

    def test_rrf_empty_qdrant(self):
        meili_hits = [
            {"id": "doc1", "content": "test1"}
        ]
        vector_hits = []

        result = reciprocal_rank_fusion(meili_hits, vector_hits, k=60, limit=10)

        assert len(result) == 1
        assert result[0][0]["id"] == "doc1"

    def test_rrf_both_empty(self):
        result = reciprocal_rank_fusion([], [], k=60, limit=10)
        assert len(result) == 0

    def test_rrf_respects_limit(self):
        meili_hits = [{"id": f"doc{i}", "content": f"test{i}"} for i in range(10)]
        vector_hits = [{"id": f"doc{i}", "content": f"test{i}"} for i in range(10, 20)]

        result = reciprocal_rank_fusion(meili_hits, vector_hits, k=60, limit=5)

        assert len(result) <= 5

    def test_rrf_scoring(self):
        """Test that RRF scores are calculated correctly."""
        meili_hits = [{"id": "doc1", "content": "test1"}]
        vector_hits = [{"id": "doc1", "content": "test1"}]

        result = reciprocal_rank_fusion(meili_hits, vector_hits, k=60, limit=10)

        # doc1 appears first in both, so score = 1/(60+1) + 1/(60+1) ≈ 0.0328
        doc, score = result[0]
        assert doc["id"] == "doc1"
        assert score > 0.03


class TestFormatAnswer:
    """Tests for the format_answer function."""

    def test_format_answer_basic(self):
        hits = [
            (
                {
                    "content": "This is test content",
                    "title": "Test Doc",
                    "page": 1,
                    "path": "/test.pdf",
                    "_formatted": {"content": "This is test content"}
                },
                0.85
            )
        ]
        terms = ["test"]

        result = format_answer("test query", hits, terms)

        assert "answer" in result
        assert "excerpts" in result
        assert "sources" in result
        assert "total_results" in result
        assert result["total_results"] == 1
        assert len(result["excerpts"]) == 1

    def test_format_answer_with_highlighting(self):
        hits = [
            (
                {
                    "content": "This is test content",
                    "title": "Test Doc",
                    "page": 1,
                    "path": "/test.pdf",
                    "_formatted": {"content": "This is test content"}
                },
                0.85
            )
        ]
        terms = ["test"]

        result = format_answer("test query", hits, terms)

        # Check that highlighting was applied
        excerpt_content = result["excerpts"][0]["content"]
        assert "**test**" in excerpt_content

    def test_format_answer_relevance_score(self):
        hits = [
            (
                {
                    "content": "Test content",
                    "title": "Test Doc",
                    "page": 1,
                    "path": "/test.pdf",
                    "_formatted": {"content": "Test content"}
                },
                0.856
            )
        ]

        result = format_answer("test", hits, [])

        # Score should be converted to percentage (0.856 * 100 = 85.6)
        assert result["excerpts"][0]["relevance_score"] == 85.6

    def test_format_answer_multiple_sources(self):
        hits = [
            (
                {
                    "content": "Content 1",
                    "title": "Doc1",
                    "page": 1,
                    "path": "/doc1.pdf",
                    "_formatted": {"content": "Content 1"}
                },
                0.9
            ),
            (
                {
                    "content": "Content 2",
                    "title": "Doc2",
                    "page": 2,
                    "path": "/doc2.pdf",
                    "_formatted": {"content": "Content 2"}
                },
                0.8
            )
        ]

        result = format_answer("test", hits, [])

        assert len(result["sources"]) == 2
        assert "/doc1.pdf (p. 1)" in result["sources"]
        assert "/doc2.pdf (p. 2)" in result["sources"]

    def test_format_answer_empty_hits(self):
        result = format_answer("test", [], [])

        assert result["total_results"] == 0
        assert len(result["excerpts"]) == 0
        assert len(result["sources"]) == 0
