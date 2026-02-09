import os

# Configuration des services
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "changeme-very-secret")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
INDEX_NAME = os.getenv("INDEX_NAME", "docs")

# Configuration du modèle et de la recherche
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

TOP_K = int(os.getenv("TOP_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "0.01"))
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
