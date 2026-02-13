from pathlib import Path
from typing import Iterator

from .base import Extractor, ExtractedPage

class TxtExtractor(Extractor):
    """
    Extracteur pour les fichiers texte (txt, md, rst). Lit le contenu du fichier en entier et le traite comme une seule page d'extraction.
    Les métadonnées associées indiquent le type de source.
    """

    # Liste des extensions de fichiers supportées par cet extracteur (ici, les fichiers .txt, .md et .rst)
    SUPPORTED_EXTENSIONS = [".txt", ".md", ".rst"]

    # Méthode d'extraction qui lit le contenu du fichier texte et le retourne comme une page d'extraction unique.
    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # Lit le contenu du fichier texte en utilisant l'encodage UTF-8.
        # Si le fichier contient des caractères invalides, ils seront remplacés par des caractères de remplacement grâce à errors="replace".
        text = file_path.read_text(encoding="utf-8", errors="replace")
        # Si le texte extrait n'est pas vide, crée une page d'extraction avec ce texte et les métadonnées associées.
        if text.strip():
            yield ExtractedPage(
                page_number=1,
                text=text,
                title=file_path.stem.replace("_", " "),
                metadata={"source_type": "txt"},
            )
