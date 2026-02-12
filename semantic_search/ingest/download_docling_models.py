#!/usr/bin/env python3
"""
Script de pré-téléchargement des modèles Docling.

Ce script télécharge tous les modèles nécessaires pour Docling :
- Modèles de détection de layout (docling-layout-heron)
- Modèles OCR (RapidOCR)

Usage:
    python download_docling_models.py

Les modèles sont sauvegardés dans le dossier spécifié par HF_HOME ou dans
./data/docling_models/ par défaut.
"""

import os
import sys
from pathlib import Path

# Ajout du chemin src au PYTHONPATH pour pouvoir importer hf_compat
sys.path.insert(0, str(Path(__file__).parent / "src"))
from ingest.extractors.hf_compat import patch_hf_hub

# Applique le patch AVANT tout import de HuggingFace/Docling
patch_hf_hub()


def _get_disk_space(path: Path) -> float:
    """Retourne l'espace disque disponible en GB."""
    try:
        import shutil
        stat = shutil.disk_usage(path)
        return stat.free / (1024**3)
    except:
        return 0.0


def _get_directory_size(path: Path) -> float:
    """Retourne la taille d'un dossier en MB."""
    try:
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total / (1024**2)
    except:
        return 0.0


def download_docling_models(models_dir: Path):
    """Télécharge tous les modèles nécessaires pour Docling."""

    print("=" * 80)
    print("TÉLÉCHARGEMENT DES MODÈLES DOCLING")
    print("=" * 80)
    print()
    print("⚠️  Attention : Cela va télécharger ~500-800 MB de modèles")
    print("   - Modèles de layout detection (~100-200 MB)")
    print("   - Modèles RapidOCR (~50-100 MB)")
    print("   - Dépendances et cache (~200-400 MB)")
    print()

    try:
        # Import de Docling (déclenche le téléchargement des modèles)
        print("📦 Import de Docling...")
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            RapidOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        print("✅ Docling importé avec succès")
        print()

        # Initialisation du converter avec OCR (télécharge les modèles)
        print("🔧 Initialisation du DocumentConverter avec OCR...")
        print("   (Cela va télécharger les modèles manquants)")
        print()

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.ocr_options = RapidOcrOptions(
            force_full_page_ocr=True,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

        print("✅ DocumentConverter initialisé")
        print()

        # Test rapide avec un PDF minimal pour forcer le chargement complet
        print("🧪 Test de chargement des modèles...")

        test_pdf = models_dir / "test.pdf"
        try:
            import fitz  # PyMuPDF
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Test Docling OCR")
            doc.save(str(test_pdf))
            doc.close()
            print(f"   Créé fichier de test : {test_pdf.name}")

            result = converter.convert(str(test_pdf))

            if result:
                md = result.document.export_to_markdown()
                print(f"✅ Modèles chargés et fonctionnels ! (extrait {len(md)} caractères)")
        finally:
            if test_pdf.exists():
                test_pdf.unlink()
                print(f"   Nettoyé : {test_pdf.name}")

        print()
        print("=" * 80)
        print("✅ TÉLÉCHARGEMENT TERMINÉ")
        print("=" * 80)
        print()
        print(f"📁 Modèles sauvegardés dans : {models_dir}")
        print(f"💾 Taille totale : ~{_get_directory_size(models_dir):.1f} MB")
        print()
        print("🎯 Prochaines étapes :")
        print("   1. Les modèles sont maintenant en cache")
        print("   2. L'extraction sera plus rapide (pas de téléchargement)")
        print("   3. Pour Docker, montez ce dossier comme volume")
        print()

        return True

    except ImportError as e:
        print(f"❌ Erreur : Docling n'est pas installé")
        print(f"   Installez avec : uv sync")
        print()
        return False

    except Exception as e:
        print(f"❌ Erreur lors du téléchargement : {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """Point d'entrée principal."""

    # Configuration du cache HuggingFace
    # Utilise data/docling_models/ pour stocker les modèles
    MODELS_DIR = Path(__file__).parent.parent / "data" / "docling_models"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Configure HuggingFace pour utiliser ce dossier
    os.environ["HF_HOME"] = str(MODELS_DIR)
    os.environ["HF_HUB_CACHE"] = str(MODELS_DIR / "hub")
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"  # Désactive symlinks sur Windows

    print(f"📁 Dossier de téléchargement : {MODELS_DIR}")
    print(f"💾 Espace disponible : {_get_disk_space(MODELS_DIR):.1f} GB")
    print()

    # Vérification de l'espace disque
    free_space = _get_disk_space(MODELS_DIR)
    if free_space < 2.0:  # 2 GB minimum
        print(f"⚠️  Attention : Espace disque faible ({free_space:.1f} GB)")
        print(f"   Recommandé : au moins 2 GB disponibles")
        print()
        response = input("Continuer quand même ? (o/N) : ")
        if response.lower() != 'o':
            print("Annulé.")
            return 1

    # Téléchargement
    success = download_docling_models(MODELS_DIR)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
