# Guide d'utilisation de Docling

## Qu'est-ce que Docling ?

[Docling](https://github.com/DS4SD/docling) est une bibliothèque développée par IBM Research pour l'extraction sémantique de documents. Elle préserve la structure et les relations dans les documents, contrairement aux extracteurs basiques qui perdent le contexte.

**Formats supportés** : PDF, DOCX, PPTX, XLSX, HTML, images (avec OCR)

## Avantages pour l'extraction de documents

### XLSX - Avant vs Après

**Avant (openpyxl):**
```
col_0: valeur1; col_1: valeur2; col_2: valeur3
col_0: valeur4; col_1: valeur5; col_2: valeur6
```

**Après (Docling):**
```markdown
=== Feuille Excel: Ventes Q1 2024 ===
Nombre de lignes: 150
Colonnes: Date, Produit, Quantité, Prix Unitaire, Total

| Date       | Produit    | Quantité | Prix Unitaire | Total    |
|------------|------------|----------|---------------|----------|
| 2024-01-15 | Widget A   | 50       | 12.50€        | 625.00€  |
| 2024-01-16 | Widget B   | 30       | 8.75€         | 262.50€  |
```

### PDF - Avant vs Après

**Avant (PyMuPDF):**
```
Date Produit Quantité Total
15/01 Widget A 50 625
16/01 Widget B 30 262
```
(Perte de structure du tableau, colonnes mélangées)

**Après (Docling):**
```markdown
# Rapport Mensuel

## Tableau des ventes

| Date       | Produit    | Quantité | Total    |
|------------|------------|----------|----------|
| 15/01/2024 | Widget A   | 50       | 625.00€  |
| 16/01/2024 | Widget B   | 30       | 262.50€  |

Total général: 887.50€
```

### DOCX - Avant vs Après

**Avant (python-docx):**
```
Titre
Introduction text...
Header1 Header2
Data1 Data2
```
(Pas de distinction titres/tableaux/paragraphes)

**Après (Docling):**
```markdown
# Titre Principal

Introduction text...

## Section 1

| Header1  | Header2  |
|----------|----------|
| Data1    | Data2    |

### Sous-section
...
```

### PPTX - Avant vs Après

**Avant (python-pptx):**
```
Slide Title
Bullet point 1
Bullet point 2
[Notes] Speaker notes
```

**Après (Docling):**
```markdown
# Slide Title

- Bullet point 1
- Bullet point 2

| Feature | Status |
|---------|--------|
| API     | ✓      |
| UI      | ✓      |

---
*Notes du présentateur: Speaker notes*
```

### Images (PNG/JPG) - Nouveau avec OCR

**Scénarios supportés :**
- 📸 Screenshots de documents
- 📄 Photos de pages de livre
- 🖼️ Captures d'écran avec tableaux
- 📊 Graphiques avec légendes
- 📋 Formulaires scannés

**Exemple d'extraction (screenshot avec tableau) :**
```markdown
# Configuration nRF24L01

| Paramètre        | Valeur | Description           |
|------------------|--------|-----------------------|
| Fréquence        | 2.4GHz | Bande ISM            |
| Débit            | 2Mbps  | Mode haute vitesse   |
| Portée           | 100m   | En champ libre       |
| Canaux           | 125    | Canaux disponibles   |

**Remarque:** Module RF low-power pour IoT
```

**Formats supportés :**
- `.png` — Captures d'écran, graphiques
- `.jpg` / `.jpeg` — Photos, documents scannés
- `.tiff` / `.tif` — Scans haute qualité
- `.bmp` — Images Windows

## Avantages généraux

- ✅ Structure markdown lisible et sémantique
- ✅ Contexte préservé (titres, sections, hiérarchies)
- ✅ Relations entre éléments maintenues
- ✅ Tables détectées et formatées correctement
- ✅ Meilleure compréhension par les LLMs
- ✅ Support multi-colonnes (PDF)
- ✅ Détection automatique du layout

## Installation

Docling et les dépendances OCR sont déjà inclus dans `pyproject.toml` :

```bash
cd ingest
uv sync  # Installe toutes les dépendances incluant Docling, pytesseract, pillow
```

**Dépendances système (Docker) :**
Le Dockerfile installe automatiquement :
- `tesseract-ocr` — Moteur OCR
- `tesseract-ocr-fra` — Support français
- `tesseract-ocr-eng` — Support anglais
- `libgomp1`, `libgl1`, `libglib2.0-0` — Bibliothèques pour Docling

**Installation locale (développement) :**
```bash
# Linux (Debian/Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang

# Windows
# Télécharger depuis https://github.com/UB-Mannheim/tesseract/wiki
```

## Test local

### 1. Tester l'extraction d'un fichier

Le script de test supporte maintenant **tous les formats** : PDF, DOCX, PPTX, XLSX

```bash
cd ingest

# Test d'un fichier unique
python test_docling_extract.py ../data/docs/rapport.pdf
python test_docling_extract.py ../data/docs/document.docx
python test_docling_extract.py ../data/docs/presentation.pptx
python test_docling_extract.py ../data/docs/tableau.xlsx

# Test de tous les fichiers d'un dossier
python test_docling_extract.py ../data/docs/
```

### 2. Exemple de sortie (XLSX)

```
📄 Test d'extraction de: rapport_ventes.xlsx (format: .xlsx)
🔧 Extracteur: XlsxExtractor
--------------------------------------------------------------------------------
✅ 3 page(s) extraite(s)

=== Page 1 ===
Métadonnées: {'source_type': 'xlsx', 'extraction_method': 'docling', 'table_index': 1}
Longueur du texte: 2458 caractères

Aperçu du contenu:
--------------------------------------------------------------------------------
| Date       | Produit    | Quantité | Prix Unitaire | Total    |
|------------|------------|----------|---------------|----------|
| 2024-01-15 | Widget A   | 50       | 12.50€        | 625.00€  |
...

📊 Statistiques:
   - Pages extraites: 3
   - Caractères totaux: 7,234
   - Moyenne par page: 2,411 caractères
   - Méthode(s) d'extraction: docling
```

### 3. Exemple de sortie (PDF)

```
📄 Test d'extraction de: rapport_technique.pdf (format: .pdf)
🔧 Extracteur: PdfExtractor
--------------------------------------------------------------------------------
✅ 15 page(s) extraite(s)

=== Page 1 ===
Métadonnées: {'source_type': 'pdf', 'extraction_method': 'docling', 'num_tables_in_page': 2}
Longueur du texte: 1843 caractères

Aperçu du contenu:
--------------------------------------------------------------------------------
# Rapport Technique

## Introduction

Ce document présente...

## Résultats

| Paramètre | Valeur | Unité |
|-----------|--------|-------|
| Tension   | 3.3    | V     |
...
```

### 4. Test en batch d'un dossier

```
📁 Scan du dossier: ../data/docs
================================================================================
Fichiers trouvés: 8

📄 Test d'extraction de: document1.pdf (format: .pdf)
✅ 5 page(s) extraite(s)
...

📄 Test d'extraction de: rapport.xlsx (format: .xlsx)
✅ 2 page(s) extraite(s)
...

================================================================================
📊 RÉSUMÉ DES TESTS
================================================================================
✅ Succès: 7/8
❌ Échecs: 1/8

Fichiers en échec:
  - corrupted_file.docx
```

## Fonctionnalités

### Fallback automatique

Si Docling échoue (fichier corrompu, format non supporté), l'extracteur bascule automatiquement sur openpyxl :

```python
try:
    # Tentative avec Docling
    yield from docling_extract(file_path)
except Exception:
    # Fallback vers openpyxl
    logger.info("Utilisation du fallback openpyxl")
    yield from openpyxl_extract(file_path)
```

### Métadonnées enrichies

Chaque page extraite contient :
- `source_type`: "xlsx"
- `table_index`: numéro de la table
- `table_name`: nom de la table (si disponible)
- `num_rows`: nombre de lignes
- `num_cols`: nombre de colonnes
- `extraction_method`: "docling" ou "openpyxl_fallback"

## Intégration Docker

Les dépendances système nécessaires sont déjà dans le Dockerfile :

```dockerfile
RUN apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \     # OpenMP pour Docling
    libgl1 \       # OpenGL pour traitement d'images
    libglib2.0-0   # GLib pour bibliothèques graphiques
```

## Rebuild après modification

```bash
# Rebuild de l'image ingestor
docker-compose build ingestor

# Redémarrage pour réindexer
docker-compose up -d ingestor

# Vérification des logs
docker-compose logs -f ingestor
```

## OCR (Reconnaissance Optique de Caractères)

### Qu'est-ce que l'OCR ?

L'OCR (Optical Character Recognition) convertit les images de texte en texte éditable. C'est essentiel pour :
- **PDF scannés** : Documents numérisés sans couche textuelle
- **Images** : Screenshots, photos de documents, graphiques
- **Documents avec images embarquées** : Tableaux/diagrammes dans DOCX/PPTX

### Formats avec OCR activé

| Format | OCR Usage |
|--------|-----------|
| **PDF** | ✅ Activé — Extrait texte des pages scannées et images |
| **DOCX** | ✅ Activé — Extrait texte des images embarquées |
| **PPTX** | ✅ Activé — Extrait texte des images dans slides |
| **Images** | ✅ **Obligatoire** — Seule méthode d'extraction |

### Backend OCR : Tesseract

**Configuration :** Docling active automatiquement l'OCR et la détection de tableaux dans sa configuration par défaut (version 2.x+). Pas besoin de configuration manuelle.

**Langues supportées :** Anglais + Français (extensible)

**Performances typiques :**
- ✅ Texte imprimé clair : 95-99% précision
- 🟡 Texte manuscrit : 60-80% précision
- 🟡 Qualité image faible : 70-85% précision

**Optimisation de la qualité :**
1. **Résolution** : Minimum 300 DPI pour documents scannés
2. **Contraste** : Fond clair, texte foncé
3. **Orientation** : Image droite (pas d'angle)
4. **Netteté** : Éviter le flou

### Exemple de test OCR

```bash
# Test sur une image
python test_docling_extract.py screenshot.png

# Test sur un PDF scanné
python test_docling_extract.py document_scanne.pdf
```

**Sortie attendue :**
```
📄 Test d'extraction de: screenshot.png (format: .png)
🔧 Extracteur: ImageExtractor
--------------------------------------------------------------------------------
✅ 1 page(s) extraite(s)

=== Page 1 ===
Métadonnées: {'source_type': 'image', 'extraction_method': 'docling_ocr', 'ocr_result': 'text_detected'}
Longueur du texte: 1234 caractères

📊 Statistiques:
   - Méthode(s) d'extraction: docling_ocr
```

### Fallback OCR

Si Docling échoue, l'extracteur d'images bascule automatiquement sur `pytesseract` :

```python
# Fallback automatique
try:
    # Tentative avec Docling OCR
    result = docling_convert(image)
except Exception:
    # Fallback vers pytesseract direct
    text = pytesseract.image_to_string(image, lang='eng+fra')
```

### Ajout de langues supplémentaires

Pour supporter d'autres langues (allemand, espagnol, etc.) :

**Dockerfile :**
```dockerfile
RUN apt-get install -y \
    tesseract-ocr-deu \  # Allemand
    tesseract-ocr-spa    # Espagnol
```

**Fallback pytesseract :**
```python
# Dans image_extractor.py, ligne 162
text = pytesseract.image_to_string(image, lang='eng+fra+deu+spa')
```

## Dépannage

### Erreur "Docling n'est pas installé"
```bash
cd ingest
uv sync  # Réinstalle les dépendances
```

### Erreur "libgomp.so.1: cannot open shared object"
Le Dockerfile manque `libgomp1`. Vérifiez que la modification du Dockerfile a été appliquée.

### Erreur "pytesseract not installed"
```bash
# Installation Python
pip install pytesseract pillow

# Installation système (Linux)
sudo apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

### Erreur "TesseractNotFoundError"
Tesseract n'est pas installé sur le système :
- **Docker** : Vérifiez que le Dockerfile contient `tesseract-ocr`
- **Local** : Installez tesseract (voir section Installation)

### OCR ne détecte aucun texte
Vérifiez la qualité de l'image :
- Résolution minimum 300 DPI
- Bon contraste (texte sombre, fond clair)
- Image droite (pas d'angle)
- Format supporté (PNG, JPG, TIFF)

### OCR très lent
C'est normal ! L'OCR est 10-50x plus lent que l'extraction directe :
- **PDF texte** : ~1 sec/page
- **PDF scanné** : ~10-30 sec/page
- **Images** : ~5-15 sec/image

Pour accélérer (si pas de contenu scanné) :
```python
# Dans pdf_extractor.py, désactiver OCR
pipeline_options.do_ocr = False
```

### Extraction vide
- Vérifiez que le fichier n'est pas corrompu
- Consultez les logs pour voir si le fallback a été utilisé
- Pour images : vérifiez qu'il y a du texte visible
- Certains formats très anciens peuvent nécessiter le fallback

## Formats supportés

✅ **Déjà intégrés avec Docling + OCR :**
- **PDF** — Layout detection, table extraction, multi-column support, **OCR activé pour PDF scannés**
- **DOCX** — Heading hierarchy, table structure, formatted lists, **OCR pour images embarquées**
- **PPTX** — Slide layout, table extraction, presenter notes, **OCR pour images dans slides**
- **XLSX** — Table structure, headers/hierarchies, cell relationships
- **Images (PNG, JPG, JPEG, TIFF, BMP)** — **Extraction complète par OCR**, détection de tableaux dans images

🔄 **Formats avec extracteurs classiques :**
- **CSV** — Extraction simple (pas besoin de Docling)
- **TXT** — Texte brut (pas besoin de Docling)

🚀 **Extension possible :**
- **HTML** — Tables et structure web
- **Images** — Avec OCR (tesseract)
- **EPUB** — Livres électroniques
- **Markdown** — Préservation de structure

Pour ajouter un nouveau format :
1. Créer un extracteur héritant de `Extractor`
2. Utiliser `DocumentConverter().convert()`
3. Exporter avec `result.document.export_to_markdown()`
4. Ajouter un fallback vers une méthode classique
5. Mettre à jour `test_docling_extract.py`

## Ressources

- [Documentation Docling](https://github.com/DS4SD/docling)
- [Paper de recherche](https://arxiv.org/abs/2408.09869)
- [Exemples d'utilisation](https://ds4sd.github.io/docling/)
