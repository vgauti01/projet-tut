from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage
from ..settings import PDF_OCR_PAGE_CHUNK, PDF_OCR_ENABLED

logger = logging.getLogger(__name__)


class PdfExtractor(Extractor):
    """
    Extracteur PDF utilisant Docling (OCR + structure).

    Pour les PDF normaux : conversion entière en une passe.
    Pour les PDF scannés (toutes pages = images) : conversion par tranches de
    PDF_OCR_PAGE_CHUNK pages afin de borner la RAM (chaque page image est
    chargée en entier par l'OCR). La pipeline Docling est initialisée une seule
    fois et réutilisée entre les tranches.

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
                pipeline_options.do_ocr = PDF_OCR_ENABLED
                pipeline_options.do_table_structure = True
                if PDF_OCR_ENABLED:
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

    @staticmethod
    def _is_scanned(file_path: Path) -> tuple[bool, int]:
        """
        Détecte si le PDF est scanné (toutes les pages sont des images sans texte natif).
        Retourne (is_scanned, page_count).
        Utilise PyMuPDF qui est déjà une dépendance du fallback.
        """
        import fitz
        try:
            with fitz.open(str(file_path)) as doc:
                page_count = doc.page_count
                # Échantillonne les 5 premières pages : si aucune n'a de texte natif → scanné
                sample = min(5, page_count)
                text_pages = sum(
                    1 for i in range(sample)
                    if doc[i].get_text("text").strip()
                )
                return text_pages == 0, page_count
        except Exception:
            return False, 0

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Extrait le contenu du PDF.
        - PDF natif : conversion entière Docling → 1 ExtractedPage.
        - PDF scanné : conversion par tranches de PDF_OCR_PAGE_CHUNK pages → 1 ExtractedPage par tranche.
        """
        is_scanned, page_count = self._is_scanned(file_path)

        if is_scanned and page_count > PDF_OCR_PAGE_CHUNK:
            logger.info(
                f"PDF scanné détecté ({page_count} pages), traitement par tranches "
                f"de {PDF_OCR_PAGE_CHUNK}: {file_path.name}"
            )
            yield from self._extract_scanned(file_path, page_count)
        else:
            yield from self._extract_full(file_path)

    def _extract_full(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Conversion entière du PDF en une seule passe Docling."""
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

    def _extract_scanned(self, file_path: Path, page_count: int) -> Iterator[ExtractedPage]:
        """
        Conversion par tranches pour PDF scannés.
        Chaque tranche est convertie indépendamment ; la pipeline Docling est réutilisée.
        """
        converter = self._get_converter()

        for start in range(1, page_count + 1, PDF_OCR_PAGE_CHUNK):
            end = min(start + PDF_OCR_PAGE_CHUNK - 1, page_count)
            try:
                result = converter.convert(str(file_path), page_range=[start, end])
                doc = result.document
                markdown = doc.export_to_markdown()

                if not markdown or not markdown.strip():
                    continue

                yield ExtractedPage(
                    page_number=start,
                    text=markdown,
                    metadata={"source_type": "pdf", "extraction_method": "docling_scanned"},
                    docling_document=doc,
                )

            except Exception as e:
                logger.warning(
                    f"Docling a échoué sur les pages {start}-{end} de {file_path}: {e}, "
                    f"fallback PyMuPDF"
                )
                yield from self._fallback_pymupdf(file_path, pages=range(start - 1, end))

    def _fallback_pymupdf(self, file_path: Path, pages=None) -> Iterator[ExtractedPage]:
        """
        Fallback PyMuPDF. `pages` : indices 0-based à extraire (None = tout le document).
        """
        import fitz

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            logger.error(f"Impossible d'ouvrir {file_path}: {e}")
            return

        try:
            page_indices = pages if pages is not None else range(len(doc))
            for i in page_indices:
                try:
                    text = doc[i].get_text("text")
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
