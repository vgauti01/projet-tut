from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class ImageExtractor(Extractor):
    """
    Extracteur pour les fichiers images (PNG, JPG, JPEG) utilisant Docling avec OCR.

    Docling utilise l'OCR (Optical Character Recognition) pour extraire le texte des images :
    - Détection automatique de texte dans l'image
    - Support des images scannées, captures d'écran, photos de documents
    - Reconnaissance de tableaux dans les images
    - Préservation de la mise en page détectée
    - Support multi-langues (selon configuration OCR)

    L'OCR est essentiel pour ce type de fichiers car les images ne contiennent pas
    de texte extractible directement.
    """
    SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Lazy loading du DocumentConverter avec OCR activé pour images."""
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import (
                    PdfPipelineOptions,
                    RapidOcrOptions,
                )
                from docling.document_converter import DocumentConverter, PdfFormatOption

                # OCR obligatoire pour les images
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = True
                pipeline_options.do_table_structure = True
                pipeline_options.ocr_options = RapidOcrOptions(
                    force_full_page_ocr=True,
                )

                # Docling traite les images via le même pipeline que les PDF
                self._converter = DocumentConverter(
                    format_options={
                        InputFormat.IMAGE: PdfFormatOption(
                            pipeline_options=pipeline_options,
                        ),
                    }
                )
                logger.info("DocumentConverter initialisé avec OCR pour images")
            except ImportError as e:
                logger.error("Docling n'est pas installé. Installez-le avec: uv add docling")
                raise ImportError(
                    "docling est requis pour l'extraction d'images. "
                    "Installez-le avec: uv add docling"
                ) from e
        return self._converter

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Extrait le texte d'une image via OCR.

        Utilise Docling pour :
        - Appliquer l'OCR sur l'image
        - Détecter et extraire les tableaux éventuels
        - Reconnaître la mise en page
        - Convertir en markdown structuré
        """
        try:
            converter = self._get_converter()

            logger.info(f"Extraction d'image avec OCR: {file_path.name}")

            # Conversion de l'image avec Docling
            result = converter.convert(str(file_path))

            # Extraction du texte complet avec structure préservée
            full_markdown = result.document.export_to_markdown()

            if not full_markdown or not full_markdown.strip():
                logger.warning(f"Aucun texte détecté dans l'image {file_path} (OCR n'a rien trouvé)")
                # On retourne quand même une page vide avec métadonnées
                # pour indiquer que le fichier a été traité
                yield ExtractedPage(
                    page_number=1,
                    text="[Image sans texte détectable]",
                    metadata={
                        "source_type": "image",
                        "extraction_method": "docling_ocr",
                        "image_format": file_path.suffix.lower(),
                        "ocr_result": "no_text_detected",
                    },
                )
                return

            yield ExtractedPage(
                page_number=1,
                text=full_markdown,
                metadata={
                    "source_type": "image",
                    "extraction_method": "docling_ocr",
                    "image_format": file_path.suffix.lower(),
                },
            )

            logger.info(f"Extraction OCR réussie: {len(full_markdown)} caractères détectés")

        except Exception as e:
            logger.error(f"Impossible d'extraire l'image {file_path} avec Docling OCR: {e}")
            # Pour les images, pas de vraie alternative sans OCR
            # On pourrait utiliser pytesseract directement en fallback
            logger.info(f"Tentative de fallback vers pytesseract pour {file_path}")
            try:
                yield from self._fallback_pytesseract_extract(file_path)
            except Exception as fallback_error:
                logger.error(f"Le fallback pytesseract a également échoué: {fallback_error}")
                # Retourne une page vide avec erreur
                yield ExtractedPage(
                    page_number=1,
                    text="[Erreur lors de l'extraction OCR]",
                    metadata={
                        "source_type": "image",
                        "extraction_method": "failed",
                        "image_format": file_path.suffix.lower(),
                        "error": str(e),
                    },
                )

    def _fallback_pytesseract_extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """
        Méthode de fallback utilisant pytesseract directement si Docling échoue.

        Note: pytesseract doit être installé séparément :
        - Linux: apt-get install tesseract-ocr
        - macOS: brew install tesseract
        - Windows: https://github.com/UB-Mannheim/tesseract/wiki
        """
        try:
            from PIL import Image
            import pytesseract

            logger.info(f"Utilisation de pytesseract pour {file_path}")

            # Ouvre l'image avec PIL
            image = Image.open(file_path)

            # Applique l'OCR avec tesseract
            # lang='eng+fra' pour supporter anglais et français
            text = pytesseract.image_to_string(image, lang='eng+fra')

            if text and text.strip():
                yield ExtractedPage(
                    page_number=1,
                    text=text.strip(),
                    metadata={
                        "source_type": "image",
                        "extraction_method": "pytesseract_fallback",
                        "image_format": file_path.suffix.lower(),
                    },
                )
            else:
                logger.warning(f"Pytesseract n'a détecté aucun texte dans {file_path}")
                yield ExtractedPage(
                    page_number=1,
                    text="[Image sans texte détectable]",
                    metadata={
                        "source_type": "image",
                        "extraction_method": "pytesseract_fallback",
                        "image_format": file_path.suffix.lower(),
                        "ocr_result": "no_text_detected",
                    },
                )

        except ImportError:
            logger.error(
                "pytesseract ou PIL n'est pas installé. "
                "Installez avec: pip install pytesseract pillow"
            )
            raise
        except Exception as e:
            logger.error(f"Erreur pytesseract: {e}")
            raise
