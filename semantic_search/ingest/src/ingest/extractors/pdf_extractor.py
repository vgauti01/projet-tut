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

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Extrait le contenu du fichier PDF en préservant la structure."""
        try:
            converter = self._get_converter()

            logger.info(f"Extraction PDF avec Docling (OCR activé): {file_path.name}")
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
                    "source_type": "pdf",
                    "extraction_method": "docling",
                },
                docling_document=doc,
            )

        except Exception as e:
            logger.error(f"Impossible d'extraire le fichier PDF {file_path} avec Docling: {e}")
            logger.info(f"Tentative de fallback vers PyMuPDF pour {file_path}")
            try:
                yield from self._fallback_pymupdf_extract(file_path)
            except Exception as fallback_error:
                logger.error(f"Le fallback PyMuPDF a également échoué: {fallback_error}")
                return

    def _fallback_pymupdf_extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Méthode de fallback utilisant PyMuPDF (fitz) si Docling échoue."""
        import fitz  # PyMuPDF

        doc = None
        try:
            doc = fitz.open(file_path)

            for i, page in enumerate(doc):
                try:
                    text = page.get_text("text")

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
                    logger.error(f"Erreur lors de l'extraction de la page {i + 1} du fichier {file_path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Impossible d'ouvrir le fichier PDF {file_path}: {e}")
            return

        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Erreur lors de la fermeture du document PDF: {e}")
