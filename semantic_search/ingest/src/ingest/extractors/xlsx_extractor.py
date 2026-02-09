from pathlib import Path
from typing import Iterator

from .base import Extractor, ExtractedPage

class XlsxExtractor(Extractor):
    """
    Extracteur pour les fichiers Excel (xlsx, xls).
    Utilise la bibliothèque openpyxl pour lire les fichiers Excel et extraire le texte de chaque feuille de calcul.
    Chaque feuille de calcul est traitée comme une page d'extraction distincte, avec son numéro de page et les métadonnées associées.
    Le texte extrait de chaque feuille est formaté en lignes, où chaque ligne correspond à une ligne de la feuille de calcul, avec les valeurs des cellules séparées par des points-virgules.
    Les en-têtes de colonnes sont utilisés pour préfixer les valeurs des cellules, afin de fournir un contexte sur le contenu de chaque cellule.
    """
    SUPPORTED_EXTENSIONS = [".xlsx", ".xls"]

    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        # import local, pour éviter d'avoir une dépendance globale à openpyxl si cet extracteur n'est pas utilisé
        from openpyxl import load_workbook

        # Parse le fichier Excel et extrait le texte de chaque feuille de calcul.
        # Chaque feuille est traitée comme une page d'extraction distincte.
        wb = load_workbook(str(file_path), read_only=True, data_only=True)

        # Parcourt chaque feuille de calcul du classeur, en utilisant la première ligne comme en-têtes de colonnes pour préfixer les valeurs des cellules.
        for sheet_idx, sheet_name in enumerate(wb.sheetnames, start=1):
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))

            if not rows:
                continue

            # Utilise la première ligne comme en-têtes de colonnes
            headers = [str(header) if header is not None else f"col_{index}" for index, header in enumerate(rows[0])]
            lines = []

            # Parcourt les lignes de la feuille de calcul à partir de la deuxième ligne (en ignorant les en-têtes), formate les données de manière lisible (clé: valeur) et les ajoute à la liste des lignes.
            for row in rows[1:]:
                parts = []
                # zip(headers, row) permet de parcourir simultanément les en-têtes et les valeurs des cellules de la ligne
                # en associant chaque valeur à son en-tête correspondant.
                for header, val in zip(headers, row):
                    if val is not None and str(val).strip():
                        parts.append(f"{header}: {val}")
                if parts:
                    lines.append("; ".join(parts))

            # Si des lignes ont été extraites de la feuille de calcul, crée une page d'extraction avec le texte formaté et les métadonnées associées.
            if lines:
                text = "\n".join(lines)
                yield ExtractedPage(
                    page_number=sheet_idx,
                    text=text,
                    metadata={"source_type": "xlsx", "sheet_name": sheet_name},
                )

        # Ferme le classeur pour libérer les ressources, même si une exception est levée pendant l'extraction.
        wb.close()
