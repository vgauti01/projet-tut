import logging
from pathlib import Path
from typing import Optional, List

from .base import Extractor
from .pdf_extractor import PdfExtractor
from .docx_extractor import DocxExtractor
from .xlsx_extractor import XlsxExtractor
from .pptx_extractor import PptxExtractor
from .csv_extractor import CsvExtractor
from .txt_extractor import TxtExtractor
from .image_extractor import ImageExtractor

# Configure le logger pour ce module, ce qui permet de suivre les opérations d'extraction et de diagnostiquer les problèmes éventuels
logger = logging.getLogger(__name__)

# Liste des classes d'extracteurs disponibles, chacune spécialisée dans un type de fichier différent (PDF, DOCX, XLSX, PPTX, CSV, TXT, Images).
_EXTRACTORS: List[type[Extractor]] = [
    PdfExtractor,
    DocxExtractor,
    XlsxExtractor,
    PptxExtractor,
    CsvExtractor,
    TxtExtractor,
    ImageExtractor,
]


def get_extractor(file_path: Path) -> Optional[Extractor]:
    """Retourne une instance d'extracteur pour le fichier donné, ou None si non supporté."""
    for extractor_cls in _EXTRACTORS:
        if extractor_cls.can_handle(file_path):
            return extractor_cls()
    return None


def supported_extensions() -> List[str]:
    """Retourne une liste plate de toutes les extensions de fichiers supportées."""
    exts: List[str] = []
    for cls in _EXTRACTORS:
        exts.extend(cls.SUPPORTED_EXTENSIONS)
    return exts
