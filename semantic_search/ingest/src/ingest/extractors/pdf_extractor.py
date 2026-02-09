from pathlib import Path
from typing import Iterator, Tuple
import fitz  # PyMuPDF, utilisé pour lire les fichiers PDF et extraire le texte de chaque page.

from .base import Extractor, ExtractedPage

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
        import fitz
        
        doc = fitz.open(file_path)
        # try/finally pour s'assurer que le document est fermé correctement après l'extraction, même en cas d'erreur lors de l'extraction du texte.
        try:
            for i, page in enumerate(doc):
                # get_text("text") extrait le texte brut de la page, sans mise en forme ni éléments graphiques.
                # Si la page est vide ou ne contient que des espaces, elle est ignorée.
                text = page.get_text("text")
                if text.strip():
                    yield ExtractedPage(
                        page_number=i + 1,
                        text=text,
                        metadata={"source_type": "pdf"},
                    )
        finally:
            # Ferme le document pour libérer les ressources, même si une exception est levée pendant l'extraction.
            doc.close()
