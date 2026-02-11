from pathlib import Path
from typing import Iterator
from contextlib import contextmanager
import logging

from .base import Extractor, ExtractedPage

logger = logging.getLogger(__name__)


@contextmanager
def open_workbook(file_path: Path):
    """Context manager pour gérer proprement l'ouverture/fermeture du workbook Excel."""
    from openpyxl import load_workbook

    wb = None
    try:
        wb = load_workbook(str(file_path), read_only=True, data_only=True)
        yield wb
    except Exception as e:
        logger.error(f"Erreur lors de l'ouverture du fichier Excel {file_path}: {e}")
        raise
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception as e:
                logger.warning(f"Erreur lors de la fermeture du workbook: {e}")


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
        # Utilise un context manager pour garantir la fermeture du workbook
        try:
            with open_workbook(file_path) as wb:
                # Parcourt chaque feuille de calcul du classeur
                for sheet_idx, sheet_name in enumerate(wb.sheetnames, start=1):
                    try:
                        ws = wb[sheet_name]
                        rows = list(ws.iter_rows(values_only=True))

                        if not rows:
                            continue

                        # Utilise la première ligne comme en-têtes de colonnes
                        headers = [
                            str(header) if header is not None else f"col_{index}"
                            for index, header in enumerate(rows[0])
                        ]
                        lines = []

                        # Parcourt les lignes de la feuille à partir de la deuxième ligne
                        for row in rows[1:]:
                            parts = []
                            for header, val in zip(headers, row):
                                if val is not None and str(val).strip():
                                    parts.append(f"{header}: {val}")
                            if parts:
                                lines.append("; ".join(parts))

                        # Si des lignes ont été extraites, crée une page d'extraction
                        if lines:
                            text = "\n".join(lines)
                            yield ExtractedPage(
                                page_number=sheet_idx,
                                text=text,
                                metadata={"source_type": "xlsx", "sheet_name": sheet_name},
                            )

                    except Exception as e:
                        logger.error(f"Erreur lors de l'extraction de la feuille '{sheet_name}': {e}")
                        continue

        except Exception as e:
            logger.error(f"Impossible d'extraire le fichier Excel {file_path}: {e}")
            return
