from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class DocxExtractor(Extractor):
    """
    Extracteur pour les fichiers DOCX utilisant Docling.

    Docling préserve la structure sémantique des documents Word :
    - Détection automatique des titres, paragraphes, listes
    - Extraction des tableaux avec leur structure préservée
    - Génération markdown structurée pour meilleur contexte RAG
    - Préservation de la hiérarchie du document

    Fallback automatique vers python-docx si Docling échoue.
    """
    SUPPORTED_EXTENSIONS = [".docx"]

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
                    "docling est requis pour l'extraction DOCX. "
                    "Installez-le avec: uv add docling"
                ) from e
        return self._converter

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Extrait le contenu du fichier DOCX en préservant la structure.

        Utilise Docling pour :
        - Analyser la structure du document (titres, sections, paragraphes)
        - Détecter et extraire les tableaux avec leur structure
        - Convertir en markdown structuré
        """
        try:
            converter = self._get_converter()

            # Conversion du document avec Docling
            result = converter.convert(str(file_path))

            # Extraction du texte complet avec structure préservée
            full_markdown = result.document.export_to_markdown()

            if not full_markdown or not full_markdown.strip():
                logger.warning(f"Aucun contenu extrait de {file_path}")
                return

            yield ExtractedPage(
                page_number=1,
                text=full_markdown,
                metadata={
                    "source_type": "docx",
                    "extraction_method": "docling",
                },
            )

        except Exception as e:
            logger.error(f"Impossible d'extraire le fichier DOCX {file_path} avec Docling: {e}")
            # Fallback vers python-docx
            logger.info(f"Tentative de fallback vers python-docx pour {file_path}")
            try:
                yield from self._fallback_python_docx_extract(file_path)
            except Exception as fallback_error:
                logger.error(f"Le fallback python-docx a également échoué: {fallback_error}")
                return

    def _fallback_python_docx_extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Méthode de fallback utilisant python-docx si Docling échoue.
        Conserve l'ancienne logique d'extraction.
        """
        from docx import Document

        # Parse le document DOCX et extrait le texte de tous les paragraphes
        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        # Concatène les paragraphes en un seul bloc de texte
        text = "\n".join(paragraphs)

        if text.strip():
            yield ExtractedPage(
                page_number=1,
                text=text,
                metadata={
                    "source_type": "docx",
                    "extraction_method": "python_docx_fallback",
                },
            )
