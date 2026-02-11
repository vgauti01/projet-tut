from pathlib import Path
from typing import Iterator
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


class PdfExtractor(Extractor):
    """
    Extracteur pour les fichiers PDF. Utilise la bibliothèque PyMuPDF (fitz)
    pour lire les fichiers PDF et extraire le texte de chaque page.
    Chaque page du PDF est traitée comme une page d'extraction distincte, avec son numéro de page et les métadonnées associées.
    """

    # Liste des extensions de fichiers supportées par cet extracteur (ici, uniquement les fichiers .pdf)
    SUPPORTED_EXTENSIONS = [".pdf"]

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # Import local pour ne charger PyMuPDF que si nécessaire
        import fitz  # PyMuPDF

        doc = None
        try:
            doc = fitz.open(file_path)

            # Extraction du texte de chaque page
            for i, page in enumerate(doc):
                try:
                    # get_text("text") extrait le texte brut de la page, sans mise en forme ni éléments graphiques
                    text = page.get_text("text")

                    # Si la page est vide ou ne contient que des espaces, elle est ignorée
                    if text.strip():
                        yield ExtractedPage(
                            page_number=i + 1,
                            text=text,
                            metadata={"source_type": "pdf"},
                        )

                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction de la page {i + 1} du fichier {file_path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Impossible d'ouvrir le fichier PDF {file_path}: {e}")
            return

        finally:
            # Ferme le document pour libérer les ressources, même si une exception est levée
            if doc is not None:
                try:
                    doc.close()
                except Exception as e:
                    logger.warning(f"Erreur lors de la fermeture du document PDF: {e}")
