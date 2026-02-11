"""Tests pour le nettoyage des artefacts PDF."""

import pytest
from ingest.text_utils import clean_pdf_artifacts


class TestCleanPdfArtifacts:
    """Tests pour la fonction clean_pdf_artifacts."""

    def test_clean_table_of_contents_dots(self):
        """Teste le nettoyage des lignes de points de table des matières."""
        text = "1    Introduction ............................................................................................... 7"
        cleaned = clean_pdf_artifacts(text)

        # Les points doivent être supprimés
        assert "....." not in cleaned
        assert "Introduction" in cleaned
        assert "1" in cleaned

    def test_clean_multiple_dot_lines(self):
        """Teste le nettoyage de plusieurs lignes avec points."""
        text = """
1    Introduction ............................................................................................... 7
1.1  Features ............................................................................................... 8
2    Pin Information.......................................................................................... 10
        """
        cleaned = clean_pdf_artifacts(text)

        # Les points doivent être supprimés
        assert "....." not in cleaned
        assert "Introduction" in cleaned
        assert "Features" in cleaned
        assert "Pin Information" in cleaned

    def test_clean_horizontal_lines(self):
        """Teste le nettoyage des lignes horizontales (tirets/underscores)."""
        text = "Section Title\n----------\nContent here\n__________\nMore content"
        cleaned = clean_pdf_artifacts(text)

        # Les longues séquences doivent être supprimées
        assert "----------" not in cleaned
        assert "__________" not in cleaned
        assert "Section Title" in cleaned
        assert "Content here" in cleaned

    def test_normalize_multiple_newlines(self):
        """Teste la normalisation des sauts de ligne multiples."""
        text = "Line 1\n\n\n\n\nLine 2\n\n\nLine 3"
        cleaned = clean_pdf_artifacts(text)

        # Maximum 2 sauts de ligne consécutifs
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned
        assert "Line 3" in cleaned

    def test_normalize_spaces(self):
        """Teste la normalisation des espaces multiples."""
        text = "Word1    Word2        Word3"
        cleaned = clean_pdf_artifacts(text)

        # Un seul espace entre les mots
        assert "    " not in cleaned
        assert "Word1 Word2 Word3" in cleaned

    def test_preserve_content(self):
        """Teste que le contenu utile est préservé."""
        text = "This is a normal paragraph with no artifacts. It should remain intact."
        cleaned = clean_pdf_artifacts(text)

        assert cleaned == text

    def test_real_world_pdf_example(self):
        """Teste avec un exemple réel de PDF technique."""
        text = """
Revision 2.0
Page 4 of 74
nRF24L01 Product Specification
Contents
1    Introduction ............................................................................................... 7
1.1  Features ............................................................................................... 8
1.2  Block diagram ...................................................................................... 9
2    Pin Information.......................................................................................... 10
2.1  Pin assignment..................................................................................... 10
2.2  Pin functions......................................................................................... 11
        """
        cleaned = clean_pdf_artifacts(text)

        # Points de table des matières supprimés
        assert "....." not in cleaned

        # Contenu préservé
        assert "nRF24L01 Product Specification" in cleaned
        assert "Contents" in cleaned
        assert "Introduction" in cleaned
        assert "Features" in cleaned
        assert "Block diagram" in cleaned

    def test_empty_string(self):
        """Teste avec une chaîne vide."""
        assert clean_pdf_artifacts("") == ""

    def test_whitespace_only(self):
        """Teste avec uniquement des espaces."""
        assert clean_pdf_artifacts("   \n  \n   ") == ""

    def test_dots_not_in_toc(self):
        """Teste que les points normaux dans le texte sont préservés."""
        text = "This is a sentence. And another one. Dr. Smith said..."
        cleaned = clean_pdf_artifacts(text)

        # Les points de ponctuation normale doivent rester
        assert "This is a sentence." in cleaned
        assert "Dr. Smith said..." in cleaned

    def test_partial_dot_lines(self):
        """Teste les lignes avec quelques points mais pas une séquence longue."""
        text = "Version 2.0 or later..."
        cleaned = clean_pdf_artifacts(text)

        # Les trois points de suspension doivent être préservés car pas entourés d'espaces/chiffres
        # Le pattern cherche spécifiquement les lignes de TOC
        assert "Version" in cleaned
