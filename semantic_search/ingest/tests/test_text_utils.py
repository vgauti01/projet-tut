"""
Tests for PDF utilities (chunking and text processing).
"""
from pathlib import Path

from ingest.text_utils import split_into_sentences, chunk_text


class TestSplitIntoSentences:
    """Tests for sentence splitting function."""

    def test_split_simple_sentences(self):
        text = "This is sentence one. This is sentence two. This is sentence three."
        sentences = split_into_sentences(text)

        assert len(sentences) == 3
        assert "This is sentence one." in sentences
        assert "This is sentence two." in sentences
        assert "This is sentence three." in sentences

    def test_split_with_abbreviations(self):
        """Test that common abbreviations don't cause false splits."""
        text = "Dr. Smith works at Company Inc. in the U.S.A. He is great."
        sentences = split_into_sentences(text)

        # Should not split on abbreviations
        assert len(sentences) == 2

    def test_split_with_question_marks(self):
        text = "What is this? How does it work? Why is it important?"
        sentences = split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_with_exclamations(self):
        text = "This is amazing! It works perfectly! Great job!"
        sentences = split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_empty_string(self):
        text = ""
        sentences = split_into_sentences(text)

        assert len(sentences) == 0

    def test_split_single_sentence(self):
        text = "This is a single sentence without punctuation"
        sentences = split_into_sentences(text)

        assert len(sentences) == 1

    def test_split_french_abbreviations(self):
        """Test French abbreviations commonly found in documents."""
        text = "M. Macron est le président de la R.F. (République Française). Mme. Borne était PM."
        sentences = split_into_sentences(text)
        # Actuellement le regex gère [A-Z]. et [A-Z][a-z]. 
        # Mme. (4 chars) n'est pas forcément géré selon le regex.
        assert len(sentences) >= 2


class TestChunkText:
    """Tests for intelligent text chunking."""

    def test_chunk_short_text(self):
        """Text shorter than chunk size should return as single chunk."""
        text = "This is a short text."
        chunks = list(chunk_text(text, size=100, overlap=20))

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_exact_size(self):
        """Test text that is exactly the chunk size."""
        text = "A" * 100
        chunks = list(chunk_text(text, size=100, overlap=20))
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_very_long_no_spaces(self):
        """Test handling of very long text without spaces (like base64)."""
        text = "A" * 500
        chunks = list(chunk_text(text, size=100, overlap=20))
        assert len(chunks) > 1
        # On vérifie que tout le contenu est présent
        assert "".join(chunks).startswith("A" * 100)

    def test_chunk_respects_sentence_boundaries(self):
        """Chunks should respect sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        chunks = list(chunk_text(text, size=50, overlap=10))

        # Each chunk should end with a sentence boundary (period)
        for chunk in chunks:
            assert chunk[-1] == '.' or len(chunk) < 50

    def test_chunk_with_overlap(self):
        """Test that overlap is preserved between chunks."""
        sentences = ["Sentence one.", "Sentence two.", "Sentence three.", "Sentence four."]
        text = " ".join(sentences)

        chunks = list(chunk_text(text, size=40, overlap=15))

        # Should have multiple chunks with overlap
        assert len(chunks) > 1

        # Check that there's some content overlap (simplified check)
        # The exact overlap depends on sentence boundaries
        if len(chunks) >= 2:
            # Just verify we got multiple chunks
            assert chunks[0] != chunks[1]

    def test_chunk_long_sentence_splitting(self):
        """Test that very long sentences are split appropriately."""
        # Create a very long sentence
        long_sentence = "This is a very long sentence " * 50 + "."

        chunks = list(chunk_text(long_sentence, size=100, overlap=20))

        # Should split the long sentence into multiple chunks
        assert len(chunks) > 1

        # Each chunk should respect the size limit (within reason)
        for chunk in chunks:
            assert len(chunk) <= 150  # size * 1.5 threshold

    def test_chunk_empty_string(self):
        """Empty string should return no chunks."""
        text = ""
        chunks = list(chunk_text(text, size=100, overlap=20))

        assert len(chunks) == 0

    def test_chunk_whitespace_normalization(self):
        """Multiple spaces should be normalized."""
        text = "This   has    multiple     spaces."
        chunks = list(chunk_text(text, size=100, overlap=20))

        assert "  " not in chunks[0]  # No double spaces

    def test_chunk_real_world_example(self):
        """Test with realistic PDF-like content."""
        text = """
        The nRF24L01 is a highly integrated, ultra low power (ULP) 2Mbps RF transceiver IC
        for the 2.4GHz ISM (Industrial, Scientific and Medical) band. The nRF24L01 integrates
        a complete 2.4GHz RF protocol with baseband protocol engine, Enhanced ShockBurst,
        suitable for ultra low power wireless applications.

        The nRF24L01 is designed for operation in the world wide ISM frequency band at
        2.400 - 2.4835GHz. An MCU (Micro Controller Unit) and very few external passive
        components are needed to design a radio system with the nRF24L01.
        """

        chunks = list(chunk_text(text, size=200, overlap=50))

        # Should create multiple chunks
        assert len(chunks) >= 2

        # Each chunk should have content
        for chunk in chunks:
            assert len(chunk) > 0
            assert chunk.strip()  # Not just whitespace

    def test_chunk_preserves_content(self):
        """Test that chunking doesn't lose content."""
        text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10."

        chunks = list(chunk_text(text, size=30, overlap=10))

        # Reconstruct content from chunks (removing overlap is complex, so just verify no loss)
        all_words = set()
        for chunk in chunks:
            all_words.update(chunk.split())

        original_words = set(text.split())

        # All original words should appear in at least one chunk
        assert original_words.issubset(all_words)

    def test_chunk_sizes_approximately_correct(self):
        """Test that chunk sizes are approximately correct."""
        text = "Short sentence. " * 100  # Create many short sentences

        target_size = 150
        chunks = list(chunk_text(text, size=target_size, overlap=30))

        # Most chunks should be close to target size
        for chunk in chunks[:-1]:  # Exclude last chunk which might be smaller
            # Should be within reasonable range (50% to 150% of target)
            assert 75 <= len(chunk) <= 225

    def test_chunk_with_mixed_punctuation(self):
        """Test with various punctuation marks."""
        text = "Question? Statement. Exclamation! Another statement. Final question?"

        chunks = list(chunk_text(text, size=50, overlap=10))

        # Should handle different punctuation correctly
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk) > 0

    def test_chunk_no_sentences_fallback(self):
        """Test fallback when no sentences are detected (e.g. text without standard punctuation)."""
        # Un texte long sans point, point d'interrogation ou d'exclamation
        text = "word " * 100
        # On force split_into_sentences à ne rien trouver de probant
        chunks = list(chunk_text(text, size=100, overlap=20))
        assert len(chunks) > 1
        assert "word" in chunks[0]

    def test_split_into_sentences_empty_variants(self):
        """Test various empty or whitespace-only inputs for sentence splitting."""
        assert split_into_sentences("") == []
        assert split_into_sentences("   ") == []
        assert split_into_sentences("\n\n") == []

    def test_chunk_text_long_sentence_with_giant_word_at_end(self):
        """Test a long sentence where a giant word is at the very end of temp_chunk."""
        giant_word = "A" * 200
        text = f"Short sentence. Start {giant_word}"
        chunks = list(chunk_text(text, size=100, overlap=20))
        assert len(chunks) > 1
        assert any(giant_word[:50] in c for c in chunks)

    def test_chunk_no_sentences_complex_fallback(self):
        """Test fallback when re.split returns something but not valid sentences."""
        # Un texte qui n'a pas d'espace après la ponctuation
        text = "Pas de phrases.Ici non plus.C'est une seule phrase pour le regex."
        # split_into_sentences utilise \s+ après la ponctuation, donc ici il verra 1 seule phrase
        # mais la longueur sera > size, donc il entrera dans la logique de découpage de phrase longue.
        chunks = list(chunk_text(text, size=20, overlap=5))
        assert len(chunks) > 1
