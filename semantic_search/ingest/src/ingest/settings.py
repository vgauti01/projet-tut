# Configuration des paramètres d'ingestion pour l'application de recherche sémantique.
# Ce fichier définit les variables d'environnement utilisées pour configurer les connexions à Meilisearch et Qdrant, ainsi que les paramètres de traitement des documents.

import os
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "changeme-very-secret")
INDEX_NAME = os.getenv("INDEX_NAME", "docs")
DOCS_DIR = os.getenv("DOCS_DIR", "./data/docs")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
