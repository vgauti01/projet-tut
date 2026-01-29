import os

# Configuration des services
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "changeme-very-secret")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
INDEX_NAME = os.getenv("INDEX_NAME", "docs")

# Configuration du modèle et de la recherche
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

TOP_K = int(os.getenv("TOP_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))  # Constante pour Reciprocal Rank Fusion
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "0.01"))  # Score minimum pour filtrer les résultats
SEARCH_MULTIPLIER = int(os.getenv("SEARCH_MULTIPLIER", "3"))  # Multiplier pour rechercher plus de résultats avant fusion

# Configuration CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
