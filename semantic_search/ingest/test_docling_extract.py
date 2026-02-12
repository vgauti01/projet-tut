#!/usr/bin/env python3
"""
Script de test pour vérifier l'extraction avec Docling.
Supporte : PDF, DOCX, PPTX, XLSX, PNG, JPG, JPEG

Usage:
    python test_docling_extract.py <fichier.pdf|docx|pptx|xlsx|png|jpg>
    python test_docling_extract.py <dossier>  # Teste tous les fichiers du dossier
"""

import sys
from pathlib import Path

# Ajout du chemin src au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Patch HuggingFace pour Windows (remplace symlinks par copies)
from ingest.extractors.hf_compat import patch_hf_hub
patch_hf_hub()

from ingest.extractors.pdf_extractor import PdfExtractor
from ingest.extractors.docx_extractor import DocxExtractor
from ingest.extractors.pptx_extractor import PptxExtractor
from ingest.extractors.xlsx_extractor import XlsxExtractor
from ingest.extractors.image_extractor import ImageExtractor


# Mapping des extensions vers les extracteurs
EXTRACTORS = {
    ".pdf": PdfExtractor,
    ".docx": DocxExtractor,
    ".pptx": PptxExtractor,
    ".xlsx": XlsxExtractor,
    ".xls": XlsxExtractor,
    ".png": ImageExtractor,
    ".jpg": ImageExtractor,
    ".jpeg": ImageExtractor,
    ".tiff": ImageExtractor,
    ".tif": ImageExtractor,
    ".bmp": ImageExtractor,
}


def test_extraction(file_path: str) -> bool:
    """Teste l'extraction d'un fichier avec Docling."""
    path = Path(file_path)

    if not path.exists():
        print(f"❌ Fichier introuvable: {file_path}")
        return False

    # Détermination de l'extracteur à utiliser
    ext = path.suffix.lower()
    extractor_class = EXTRACTORS.get(ext)

    if not extractor_class:
        print(f"❌ Format non supporté: {ext}")
        print(f"   Formats supportés: {', '.join(EXTRACTORS.keys())}")
        return False

    print(f"📄 Test d'extraction de: {path.name} (format: {ext})")
    print(f"🔧 Extracteur: {extractor_class.__name__}")
    print("-" * 80)

    extractor = extractor_class()

    try:
        pages = list(extractor.extract(path))

        if not pages:
            print("⚠️  Aucune page extraite")
            return False

        print(f"✅ {len(pages)} page(s) extraite(s)\n")

        for page in pages:
            print(f"=== Page {page.page_number} ===")
            print(f"Métadonnées: {page.metadata}")
            print(f"Longueur du texte: {len(page.text)} caractères")
            print("\nAperçu du contenu:")
            print("-" * 80)
            # Affiche les 1000 premiers caractères
            preview = page.text[:1000]
            print(preview)
            if len(page.text) > 1000:
                print(f"\n... ({len(page.text) - 1000} caractères supplémentaires)")
            print("\n" + "=" * 80 + "\n")

        # Statistiques globales
        total_chars = sum(len(p.text) for p in pages)
        print("\n📊 Statistiques:")
        print(f"   - Pages extraites: {len(pages)}")
        print(f"   - Caractères totaux: {total_chars:,}")
        print(f"   - Moyenne par page: {total_chars // len(pages):,} caractères")

        # Vérification de la méthode d'extraction
        extraction_methods = {p.metadata.get('extraction_method', 'unknown') for p in pages}
        print(f"   - Méthode(s) d'extraction: {', '.join(extraction_methods)}")

        if any('fallback' in method for method in extraction_methods):
            print("\n⚠️  AVERTISSEMENT: Fallback utilisé (Docling a échoué)")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de l'extraction: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_directory(dir_path: str) -> dict:
    """Teste tous les fichiers supportés d'un dossier."""
    path = Path(dir_path)

    if not path.is_dir():
        print(f"❌ Dossier introuvable: {dir_path}")
        return {}

    print(f"📁 Scan du dossier: {path}")
    print("=" * 80)

    # Collecte des fichiers
    files = []
    for ext in EXTRACTORS.keys():
        files.extend(path.glob(f"*{ext}"))

    if not files:
        print(f"⚠️  Aucun fichier supporté trouvé dans {dir_path}")
        print(f"   Formats recherchés: {', '.join(EXTRACTORS.keys())}")
        return {}

    print(f"Fichiers trouvés: {len(files)}\n")

    # Test de chaque fichier
    results = {}
    for file in sorted(files):
        print("\n" + "=" * 80)
        success = test_extraction(str(file))
        results[str(file)] = success

    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)

    successes = sum(1 for v in results.values() if v)
    failures = len(results) - successes

    print(f"✅ Succès: {successes}/{len(results)}")
    print(f"❌ Échecs: {failures}/{len(results)}")

    if failures > 0:
        print("\nFichiers en échec:")
        for file, success in results.items():
            if not success:
                print(f"  - {Path(file).name}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_docling_extract.py <fichier>")
        print("  python test_docling_extract.py <dossier>")
        print()
        print(f"Formats supportés: {', '.join(EXTRACTORS.keys())}")
        sys.exit(1)

    target = sys.argv[1]
    path = Path(target)

    if path.is_file():
        success = test_extraction(target)
        sys.exit(0 if success else 1)
    elif path.is_dir():
        results = test_directory(target)
        all_success = all(results.values()) if results else False
        sys.exit(0 if all_success else 1)
    else:
        print(f"❌ Chemin invalide: {target}")
        sys.exit(1)
