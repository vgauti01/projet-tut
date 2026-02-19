from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class PdfExtractor(Extractor):
    """
    Extracteur pour les fichiers PDF utilisant Docling avec OCR.

    Docling offre une extraction PDF avancée :
    - Détection automatique de la mise en page (layout)
    - Extraction des tableaux avec structure préservée
    - OCR activé avec force_full_page_ocr pour PDF scannés/images
    - Préservation de l'ordre de lecture logique
    - Backend OCR : RapidOCR (inclus avec Docling)

    Fallback automatique vers PyMuPDF (fitz) si Docling échoue.
    """
    SUPPORTED_EXTENSIONS = [".pdf"]

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Lazy loading du DocumentConverter avec OCR activé."""
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import (
                    PdfPipelineOptions,
                    RapidOcrOptions,
                )
                from docling.document_converter import DocumentConverter, PdfFormatOption

                # Configuration OCR pour PDF (y compris PDF scannés / images)
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = True
                pipeline_options.do_table_structure = True
                # RapidOCR est déjà installé avec Docling, pas de dépendance supplémentaire
                pipeline_options.ocr_options = RapidOcrOptions(
                    force_full_page_ocr=False,  # Docling détecte automatiquement les pages/régions image
                )

                self._converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=pipeline_options,
                        )
                    }
                )
            except ImportError as e:
                logger.error("Docling n'est pas installé. Installez-le avec: uv add docling")
                raise ImportError(
                    "docling est requis pour l'extraction PDF. "
                    "Installez-le avec: uv add docling"
                ) from e
        return self._converter

    @staticmethod
    def _get_page_count(file_path: Path) -> int:
        """Retourne le nombre de pages du PDF via PyMuPDF (léger, sans chargement complet)."""
        import fitz
        with fitz.open(file_path) as doc:
            return doc.page_count

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Extrait le contenu du PDF page par page pour limiter la RAM.
        Chaque page est convertie indépendamment par Docling puis libérée.
        Fallback vers PyMuPDF si Docling échoue sur une page.
        """
        try:
            page_count = self._get_page_count(file_path)
        except Exception as e:
            logger.error(f"Impossible de lire le nombre de pages de {file_path}: {e}")
            yield from self._fallback_pymupdf_extract(file_path)
            return

        logger.info(f"Extraction PDF avec Docling page par page ({page_count} pages): {file_path.name}")

        converter = self._get_converter()

        for page_num in range(1, page_count + 1):
            try:
                result = converter.convert(
                    str(file_path),
                    page_ranges=[(page_num, page_num)],
                )
                doc = result.document
                markdown = doc.export_to_markdown()

                if not markdown or not markdown.strip():
                    continue

                yield ExtractedPage(
                    page_number=page_num,
                    text=markdown,
                    metadata={
                        "source_type": "pdf",
                        "extraction_method": "docling",
                    },
                    docling_document=doc,
                )

            except Exception as e:
                logger.warning(f"Docling a échoué sur la page {page_num} de {file_path}: {e}, fallback PyMuPDF")
                try:
                    yield from self._fallback_pymupdf_extract(file_path, pages=[page_num - 1])
                except Exception as fallback_error:
                    logger.error(f"Fallback PyMuPDF échoué pour la page {page_num}: {fallback_error}")

    def _fallback_pymupdf_extract(self, file_path: Path, pages: list[int] | None = None) -> Iterator[ExtractedPage]:
        """
        Fallback PyMuPDF. Si `pages` est fourni (indices 0-based), seules ces pages sont extraites.
        Sinon toutes les pages sont traitées.
        """
        import fitz  # PyMuPDF

        doc = None
        try:
            doc = fitz.open(file_path)
            page_indices = pages if pages is not None else range(len(doc))

            for i in page_indices:
                try:
                    text = doc[i].get_text("text")
                    if text.strip():
                        yield ExtractedPage(
                            page_number=i + 1,
                            text=text,
                            metadata={
                                "source_type": "pdf",
                                "extraction_method": "pymupdf_fallback",
                            },
                        )
                except Exception as e:
                    logger.error(f"Erreur extraction page {i + 1} de {file_path}: {e}")

        except Exception as e:
            logger.error(f"Impossible d'ouvrir le fichier PDF {file_path}: {e}")

        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Erreur fermeture PDF {file_path}: {e}")
