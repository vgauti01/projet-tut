import csv
from pathlib import Path
from typing import Iterator

from .base import Extractor, ExtractedPage

# Taille du batch de lignes à regrouper dans une page lors de l'extraction d'un fichier CSV.
# Cela permet de limiter la taille du texte extrait par page, facilitant ainsi le traitement et l'analyse.
# Ex: avec BATCH_SIZE=500, chaque page contiendra jusqu'à 500 lignes du CSV, formatées de manière lisible.
BATCH_SIZE = 500

class CsvExtractor(Extractor):
    """ 
    Extracteur pour les fichiers CSV.
    Lit les données ligne par ligne et les regroupe en "pages" de taille définie par BATCH_SIZE.
    Chaque page contient un certain nombre de lignes du CSV, formatées de manière lisible.
    Les métadonnées associées indiquent le type de source.
    """

    # Liste des extensions de fichiers supportées par cet extracteur (ici, uniquement les fichiers .csv)
    SUPPORTED_EXTENSIONS = [".csv"]

    # Implémentation de la méthode d'extraction pour les fichiers CSV.
    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # Ouvre le fichier CSV en mode lecture, avec encodage UTF-8 et remplacement des caractères invalides
        # En python, l'utilisation de "with" garantit que le fichier sera correctement fermé après son utilisation, même en cas d'erreur.
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            # Parse le fichier CSV en utilisant csv.DictReader, qui lit chaque ligne comme un dictionnaire avec les en-têtes comme clés
            reader = csv.DictReader(file)
            # Regroupe les lignes du CSV en batches de taille BATCH_SIZE pour créer des pages d'extraction
            batch: list[str] = []
            # Numéro de la page courante
            batch_num = 1

            # Parcourt chaque ligne du CSV, formate les données de manière lisible (clé: valeur) et les ajoute au batch actuel.
            for row in reader:
                parts = []
                for key, val in row.items():
                    if val and val.strip():
                        parts.append(f"{key}: {val}")
                if parts:
                    batch.append("; ".join(parts))

                # Lorsque le batch atteint la taille définie par BATCH_SIZE, crée une page d'extraction avec le texte formaté et les métadonnées,
                # puis réinitialise le batch pour la prochaine page.
                if len(batch) >= BATCH_SIZE:
                    # En python, la fonction "yield" permet de créer un générateur, qui produit des éléments un par un à la demande, plutôt que de stocker tous les éléments en mémoire à la fois.
                    yield ExtractedPage(
                        page_number=batch_num,
                        text="\n".join(batch),
                        metadata={"source_type": "csv"},
                    )
                    batch = []
                    batch_num += 1

            # Si des lignes restent dans le batch après la boucle, crée une dernière page d'extraction avec ces lignes restantes.
            if batch:
                yield ExtractedPage(
                    page_number=batch_num,
                    text="\n".join(batch),
                    metadata={"source_type": "csv"},
                )
