"""
Configuration des paramètres de l'application et des services utilisés.
Ce module centralise la configuration de l'application, en utilisant des variables d'environnement avec des valeurs par défaut pour permettre une flexibilité et une personnalisation facile lors du déploiement dans différents environnements (développement, staging, production).
Les paramètres incluent les URLs et clés d'API pour les services de recherche (Meilisearch et Qdrant), les modèles d'embeddings et de reranking, les paramètres de recherche, la configuration CORS, et les paramètres pour le service de langage (LLM).
"""

import os

# Configuration des services
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "changeme-very-secret")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
INDEX_NAME = os.getenv("INDEX_NAME", "docs")

# Configuration du modèle et de la recherche
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Paramètres de la recherche
# TOP_K : nombre de résultats à retourner après le reranking
TOP_K = int(os.getenv("TOP_K", "5"))
# RRF_K : nombre de résultats à considérer pour le Reciprocal Rank Fusion (RRF) lors du reranking.
RRF_K = int(os.getenv("RRF_K", "60"))
# MIN_SCORE_THRESHOLD : score minimum pour filtrer les résultats après le reranking. Les résultats avec un score inférieur à ce seuil seront exclus de la réponse finale.
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "0.01"))
# SEARCH_MULTIPLIER : facteur multiplicateur pour le nombre de résultats à récupérer initialement de Meilisearch et Qdrant avant le reranking.
# Par exemple, si TOP_K est 5 et SEARCH_MULTIPLIER est 3, alors 15 résultats seront récupérés de chaque moteur de recherche avant d'être fusionnés et rerankés pour obtenir les 5 meilleurs résultats finaux.
SEARCH_MULTIPLIER = int(os.getenv("SEARCH_MULTIPLIER", "3"))

# Configuration CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# Configuration LLM
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "")
LLM_N_CTX = int(os.getenv("LLM_N_CTX", "2048"))
LLM_N_THREADS = int(os.getenv("LLM_N_THREADS", "0"))  # 0 = auto
LLM_GPU_LAYERS = int(os.getenv("LLM_GPU_LAYERS", "0"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_MAX_HISTORY = int(os.getenv("LLM_MAX_HISTORY", "5"))
