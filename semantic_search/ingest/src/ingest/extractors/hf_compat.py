"""
Compatibilité HuggingFace Hub pour Windows sans Mode Développeur.

Sur Windows, HuggingFace Hub utilise des symlinks pour son cache de modèles.
Sans le Mode Développeur ou les privilèges administrateur, la création de
symlinks échoue avec WinError 1314.

Ce module remplace la création de symlinks par une copie de fichiers,
ce qui fonctionne sans privilèges spéciaux (au prix d'un peu plus d'espace disque).

Usage: importer ce module AVANT d'importer Docling.
    from .hf_compat import patch_hf_hub
    patch_hf_hub()
"""

import os
import sys
import shutil
import logging

logger = logging.getLogger(__name__)

_patched = False


def patch_hf_hub():
    """
    Remplace la création de symlinks de HuggingFace Hub par des copies de fichiers.
    Nécessaire sur Windows sans Mode Développeur.
    Idempotent : peut être appelé plusieurs fois sans effet.
    """
    global _patched
    if _patched:
        return

    # Uniquement nécessaire sur Windows
    if sys.platform != "win32":
        _patched = True
        return

    # Supprime le warning de symlinks
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    try:
        import huggingface_hub.file_download as hf_download

        original_create_symlink = hf_download._create_symlink

        def _create_symlink_or_copy(src, dst, new_blob=False):
            """Crée un symlink ou copie le fichier si les symlinks ne sont pas supportés."""
            try:
                original_create_symlink(src, dst, new_blob=new_blob)
            except OSError:
                # Symlinks non supportés : on copie le fichier à la place
                src_str, dst_str = str(src), str(dst)
                if new_blob:
                    shutil.copy2(src_str, dst_str)
                elif not os.path.exists(dst_str):
                    shutil.copy2(src_str, dst_str)

        hf_download._create_symlink = _create_symlink_or_copy
        _patched = True
        logger.debug("HuggingFace Hub patché : symlinks remplacés par des copies")

    except (ImportError, AttributeError) as e:
        logger.warning(f"Impossible de patcher HuggingFace Hub : {e}")
