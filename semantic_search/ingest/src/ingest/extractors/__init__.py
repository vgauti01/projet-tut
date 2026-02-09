from .base import Extractor, ExtractedPage
from .registry import get_extractor, supported_extensions

# Expose les classes et fonctions principales pour faciliter les imports
__all__ = ["Extractor", "ExtractedPage", "get_extractor", "supported_extensions"]
