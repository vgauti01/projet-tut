#!/usr/bin/env python3
"""
Script pour télécharger les modèles Hugging Face dans data/models/
Usage: python download_models.py
"""

from sentence_transformers import SentenceTransformer, CrossEncoder
from pathlib import Path

# Répertoire de destination
MODELS_DIR = Path(__file__).parent / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Modèles à télécharger
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

print(f"📥 Téléchargement des modèles dans : {MODELS_DIR}")
print()

# Télécharger le modèle d'embeddings
print(f"1️⃣  Téléchargement de {EMBED_MODEL}...")
embed_model = SentenceTransformer(EMBED_MODEL, cache_folder=str(MODELS_DIR))
print(f"   ✅ Téléchargé : {EMBED_MODEL}")
print()

# Télécharger le modèle de reranking
print(f"2️⃣  Téléchargement de {RERANK_MODEL}...")
rerank_model = CrossEncoder(RERANK_MODEL, cache_folder=str(MODELS_DIR))
print(f"   ✅ Téléchargé : {RERANK_MODEL}")
print()

print("🎉 Tous les modèles ont été téléchargés avec succès !")
print(f"📂 Emplacement : {MODELS_DIR.absolute()}")
