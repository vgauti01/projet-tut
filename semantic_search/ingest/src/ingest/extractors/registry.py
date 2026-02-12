import logging
from pathlib import Path
from typing import Dict, Optional, List

from .base import Extractor
from .pdf_extractor import PdfExtractor
from .docx_extractor import DocxExtractor
from .xlsx_extractor import XlsxExtractor
from .pptx_extractor import PptxExtractor
from .csv_extractor import CsvExtractor
from .txt_extractor import TxtExtractor
from .image_extractor import ImageExtractor

logger = logging.getLogger(__name__)

# Liste des classes d'extracteurs disponibles
_EXTRACTORS: List[type[Extractor]] = [
    PdfExtractor,
    DocxExtractor,
    XlsxExtractor,
    PptxExtractor,
    CsvExtractor,
    TxtExtractor,
    ImageExtractor,
]

# Cache singleton : une instance par classe d'extracteur
# Évite de recréer un DocumentConverter Docling (coûteux) pour chaque fichier
_instances: Dict[type, Extractor] = {}


def get_extractor(file_path: Path) -> Optional[Extractor]:
    """Retourne une instance (singleton) d'extracteur pour le fichier donné, ou None si non supporté."""
    for extractor_cls in _EXTRACTORS:
        if extractor_cls.can_handle(file_path):
            if extractor_cls not in _instances:
                _instances[extractor_cls] = extractor_cls()
            return _instances[extractor_cls]
    return None


def supported_extensions() -> List[str]:
    """Retourne une liste plate de toutes les extensions de fichiers supportées."""
    exts: List[str] = []
    for cls in _EXTRACTORS:
        exts.extend(cls.SUPPORTED_EXTENSIONS)
    return exts
