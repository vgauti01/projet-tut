from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class PdfExtractor(Extractor):
    """
    Extracteur PDF utilisant Docling (OCR + structure) pour une conversion complète.
    Fallback automatique vers PyMuPDF page par page si Docling échoue.
    """
    SUPPORTED_EXTENSIONS = [".pdf"]

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Lazy loading du DocumentConverter avec OCR activé."""
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
                from docling.document_converter import DocumentConverter, PdfFormatOption

                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = True
                pipeline_options.do_table_structure = True
                pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=False)

                self._converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                    }
                )
            except ImportError as e:
                raise ImportError(
                    "docling est requis pour l'extraction PDF. "
                    "Installez-le avec: uv add docling"
                ) from e
        return self._converter

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Convertit le PDF entier avec Docling, yield un unique ExtractedPage."""
        try:
            converter = self._get_converter()
            logger.info(f"Extraction PDF avec Docling: {file_path.name}")
            result = converter.convert(str(file_path))
            doc = result.document
            markdown = doc.export_to_markdown()

            if markdown and markdown.strip():
                yield ExtractedPage(
                    page_number=1,
                    text=markdown,
                    metadata={"source_type": "pdf", "extraction_method": "docling"},
                    docling_document=doc,
                )
            else:
                logger.warning(f"Aucun contenu extrait de {file_path} avec Docling")

        except Exception as e:
            logger.error(f"Docling a échoué pour {file_path}: {e}")
            logger.info(f"Fallback PyMuPDF pour {file_path.name}")
            yield from self._fallback_pymupdf(file_path)

    def _fallback_pymupdf(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Fallback PyMuPDF : extraction page par page."""
        import fitz

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            logger.error(f"Impossible d'ouvrir {file_path}: {e}")
            return

        try:
            for i, page in enumerate(doc):
                try:
                    text = page.get_text("text")
                    if text.strip():
                        yield ExtractedPage(
                            page_number=i + 1,
                            text=text,
                            metadata={"source_type": "pdf", "extraction_method": "pymupdf_fallback"},
                        )
                except Exception as e:
                    logger.error(f"Erreur page {i + 1} de {file_path}: {e}")
        finally:
            doc.close()
