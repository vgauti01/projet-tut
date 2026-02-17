from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class HtmlExtractor(Extractor):
    """
    Extracteur pour les fichiers HTML utilisant Docling.

    Docling préserve la structure sémantique des pages HTML :
    - Détection automatique des sections, titres, paragraphes
    - Extraction des tableaux avec leur structure préservée
    - Génération markdown structurée pour meilleur contexte RAG
    - Nettoyage du balisage HTML pour ne conserver que le contenu
    - Préservation de la hiérarchie du document

    Fallback automatique vers BeautifulSoup si Docling échoue.
    """
    SUPPORTED_EXTENSIONS = [".html", ".htm"]

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Lazy loading du DocumentConverter."""
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter
                self._converter = DocumentConverter()
            except ImportError as e:
                logger.error("Docling n'est pas installé. Installez-le avec: uv add docling")
                raise ImportError(
                    "docling est requis pour l'extraction HTML. "
                    "Installez-le avec: uv add docling"
                ) from e
        return self._converter

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Extrait le contenu du fichier HTML en préservant la structure.

        Utilise Docling pour :
        - Analyser la structure HTML (titres, sections, paragraphes)
        - Détecter et extraire les tableaux avec leur structure
        - Convertir en markdown structuré
        - Nettoyer le contenu des balises de script, style, etc.
        """
        try:
            converter = self._get_converter()

            logger.info(f"Extraction HTML avec Docling: {file_path.name}")
            result = converter.convert(str(file_path))
            doc = result.document

            # Extraction du document complet en markdown
            full_markdown = doc.export_to_markdown()

            if not full_markdown or not full_markdown.strip():
                logger.warning(f"Aucun contenu extrait de {file_path} avec Docling")
                return

            yield ExtractedPage(
                page_number=1,
                text=full_markdown,
                metadata={
                    "source_type": "html",
                    "extraction_method": "docling",
                },
                docling_document=doc,
            )

        except Exception as e:
            logger.error(f"Impossible d'extraire le fichier HTML {file_path} avec Docling: {e}")
            logger.info(f"Tentative de fallback vers BeautifulSoup pour {file_path}")
            try:
                yield from self._fallback_beautifulsoup_extract(file_path)
            except Exception as fallback_error:
                logger.error(f"Le fallback BeautifulSoup a également échoué: {fallback_error}")
                return

    def _fallback_beautifulsoup_extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Méthode de fallback utilisant BeautifulSoup si Docling échoue.

        Extraction basique du texte en supprimant les balises HTML :
        - Suppression des scripts, styles, et autres éléments non-textuels
        - Extraction du texte visible
        - Nettoyage des espaces multiples
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            logger.error("BeautifulSoup n'est pas installé. Installez-le avec: uv add beautifulsoup4")
            raise ImportError(
                "beautifulsoup4 est requis pour le fallback HTML. "
                "Installez-le avec: uv add beautifulsoup4"
            ) from e

        try:
            # Lecture du fichier HTML
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()

            # Parse le HTML avec BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Supprime les scripts, styles et autres éléments non pertinents
            for element in soup(['script', 'style', 'meta', 'link', 'noscript', 'head']):
                element.decompose()

            # Extrait le texte visible
            text = soup.get_text(separator='\n', strip=True)

            # Nettoie les lignes vides multiples
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)

            if clean_text.strip():
                yield ExtractedPage(
                    page_number=1,
                    text=clean_text,
                    metadata={
                        "source_type": "html",
                        "extraction_method": "beautifulsoup_fallback",
                    },
                )
            else:
                logger.warning(f"Aucun contenu textuel extrait de {file_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction HTML avec BeautifulSoup: {e}")
            raise
