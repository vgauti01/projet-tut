from pathlib import Path
from typing import Iterator

from .base import Extractor, ExtractedPage

class PptxExtractor(Extractor):
    """
    Extracteur pour les fichiers PPTX. Utilise la bibliothèque python-pptx pour lire le contenu des présentations PowerPoint.
    Il extrait le texte de chaque diapositive, y compris les formes contenant du texte et les notes du présentateur.
    Chaque diapositive est traitée comme une page d'extraction distincte, avec son numéro de page et les métadonnées associées.
    """

    # Liste des extensions de fichiers supportées par cet extracteur (ici, uniquement les fichiers .pptx)
    SUPPORTED_EXTENSIONS = [".pptx"]

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # import local, pour éviter d'avoir une dépendance globale à python-pptx si cet extracteur n'est pas utilisé
        from pptx import Presentation

        # Parse la présentation PPTX et extrait le texte de chaque diapositive.
        prs = Presentation(str(file_path))

        for slide_idx, slide in enumerate(prs.slides, start=1):
            parts = []

            # Extraction du texte des formes
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            parts.append(text)

            # Extraction des notes du présentateur
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    parts.append(f"[Notes] {notes}")

            if parts:
                text = "\n".join(parts)
                yield ExtractedPage(
                    page_number=slide_idx,
                    text=text,
                    metadata={"source_type": "pptx"},
                )
