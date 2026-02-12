from .hf_compat import patch_hf_hub

# Patch HuggingFace Hub AVANT tout import de Docling (symlinks Windows)
patch_hf_hub()

from .base import Extractor, ExtractedPage
from .registry import get_extractor, supported_extensions

# Expose les classes et fonctions principales pour faciliter les imports
__all__ = ["Extractor", "ExtractedPage", "get_extractor", "supported_extensions"]
