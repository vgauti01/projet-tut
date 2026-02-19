# Configuration des paramètres d'ingestion pour l'application de recherche sémantique.
# Ce fichier définit les variables d'environnement utilisées pour configurer les connexions à Meilisearch et Qdrant, ainsi que les paramètres de traitement des documents.

import os
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "changeme-very-secret")
INDEX_NAME = os.getenv("INDEX_NAME", "docs")
DOCS_DIR = os.getenv("DOCS_DIR", "./data/docs")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
CHUNK_MAX_TOKENS = int(os.getenv("CHUNK_MAX_TOKENS", "512"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.getenv("EMBED_MODEL", "google/embeddinggemma-300m")
FILE_BATCH_SIZE = int(os.getenv("FILE_BATCH_SIZE", "200"))  # chunks max envoyés par batch à l'indexation
PDF_OCR_PAGE_CHUNK = int(os.getenv("PDF_OCR_PAGE_CHUNK", "10"))  # pages par appel Docling pour PDF scannés
PDF_OCR_ENABLED = os.getenv("PDF_OCR_ENABLED", "true").lower() == "true"
