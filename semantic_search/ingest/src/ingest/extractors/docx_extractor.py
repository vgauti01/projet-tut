from pathlib import Path
from typing import Iterator

from .base import Extractor, ExtractedPage

class DocxExtractor(Extractor):
    """
    Extracteur pour les fichiers DOCX. Utilise la bibliothèque python-docx pour lire le contenu des documents Word.
    Il extrait le texte de tous les paragraphes et les concatène en un seul bloc de texte.
    Chaque document est traité comme une seule page (page_number=1) car les documents Word n'ont pas de structure de page fixe.
    Le texte extrait est nettoyé pour supprimer les espaces superflus.
    """

    # Liste des extensions de fichiers supportées par cet extracteur (ici, uniquement les fichiers .docx)
    SUPPORTED_EXTENSIONS = [".docx"]

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # import local, pour éviter d'avoir une dépendance globale à python-docx si cet extracteur n'est pas utilisé
        # La bibliothèque python-docx est utilisée pour lire les fichiers DOCX et extraire le texte des paragraphes.
        from docx import Document

        # Parse le document DOCX et extrait le texte de tous les paragraphes. Les paragraphes vides sont ignorés.
        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Concatène les paragraphes extraits en un seul bloc de texte, en séparant les paragraphes par des sauts de ligne.
        text = "\n".join(paragraphs)

        # Si le texte extrait n'est pas vide, crée une page d'extraction avec ce texte et les métadonnées associées.
        if text.strip():
            yield ExtractedPage(
                page_number=1,
                text=text,
                metadata={"source_type": "docx"},
            )
