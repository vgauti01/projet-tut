# Assistant Documentaire Hybride (RAG System)

Systeme de recherche hybride combinant BM25 (Meilisearch) et recherche vectorielle (Qdrant), avec reranking par cross-encoder et generation de reponses par LLM local (optionnel). Le systeme permet d'interroger efficacement une collection de documents multi-formats via une interface conversationnelle en streaming.

## Fonctionnalites

- **Recherche hybride** : Combine recherche par mots-cles (BM25) et recherche semantique (embeddings vectoriels)
- **Reciprocal Rank Fusion (RRF)** : Algorithme de fusion des resultats des deux moteurs
- **Reranking cross-encoder** : Affinage de la pertinence via `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- **Generation LLM (optionnel)** : Reponses generees par un modele local (Qwen3, LLaMA, etc.) via llama-cpp-python
- **Streaming SSE** : Reponses en temps reel token par token
- **Chat conversationnel** : Sessions avec historique de conversation
- **Multi-format** : PDF, DOCX, PPTX, XLSX, CSV, TXT, HTML, Images (OCR)
- **Extraction intelligente** : Docling (ML) avec fallback PyMuPDF pour les PDF
- **Chunking intelligent** : Decoupage respectant les limites de phrases avec overlap
- **Interface moderne** : React + TypeScript + Tailwind CSS, mode sombre, metriques visuelles
- **Monitoring** : Prometheus + Grafana + cAdvisor (optionnel)
- **Health checks** : Endpoints liveness, readiness et deep diagnostics

## Prerequis

- Docker et Docker Compose
- 4 GB de RAM minimum
- 2 GB d'espace disque

## Installation

1. **Configuration**
```bash
cp .env.example .env
# Editer .env avec vos cles et parametres
```

2. **Ajouter vos documents**

Placer vos fichiers (PDF, DOCX, PPTX, XLSX, CSV, TXT, HTML, images) dans `./data/docs/`

3. **Demarrer les services**
```bash
# Sans monitoring
docker compose up -d

# Avec monitoring (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

4. **Indexer les documents**
```bash
docker compose --profile ingestor run --rm ingestor
```

5. **Acceder a l'interface**
- Frontend : http://localhost:5173
- API docs : http://localhost:8000/docs
- Grafana : http://localhost:3000 (si monitoring actif)

### LLM local (optionnel)

Pour activer la generation de reponses, placer un modele GGUF dans `./data/models/` et configurer dans `.env` :
```bash
LLM_MODEL_PATH=/app/models/Qwen3-1.7B.Q6_K.gguf
LLM_N_CTX=8192
```

## Architecture

```
┌─────────────────┐
│   Frontend      │  React + TypeScript + Tailwind
│  (port 5173)    │
└────────┬────────┘
         │
         v
┌─────────────────┐     ┌─────────────┐
│   API FastAPI   │ --> │  LLM local  │  (optionnel)
│  (port 8000)    │     │  llama-cpp  │
└────┬───────┬────┘     └─────────────┘
     │       │
     v       v
┌─────────┐ ┌─────────┐
│ Meili   │ │ Qdrant  │
│ (BM25)  │ │(Vector) │
└─────────┘ └─────────┘
```

### Composants

| Service | Role | Port |
|---------|------|------|
| **Frontend** | Interface React avec mode chat et recherche | 5173 |
| **API** | Backend FastAPI : recherche hybride, reranking, LLM, streaming | 8000 |
| **Meilisearch** | Moteur BM25 (recherche par mots-cles) | 7700 |
| **Qdrant** | Base vectorielle (recherche semantique) | 6333 |
| **Ingestor** | Extraction, chunking et indexation des documents | - |
| **Prometheus** | Collecte de metriques (profil monitoring) | 9090 |
| **Grafana** | Visualisation des metriques (profil monitoring) | 3000 |

## Flux de donnees

### Indexation
```
Documents (PDF, DOCX, ...) --> Extraction (Docling / PyMuPDF)
    --> Chunking intelligent --> Embeddings (multilingual-e5-base)
        --> Meilisearch (texte) + Qdrant (vecteurs)
```

### Recherche
```
Question utilisateur
        |
    Embeddings
        |
   +----+-----+
   |          |
Meili (BM25)  Qdrant (Vector)
   |          |
   +----+-----+
        |
  RRF Fusion
        |
  Cross-encoder Reranking
        |
  (optionnel) LLM Generation avec contexte RAG
        |
  Reponse streamee (SSE)
```

## Configuration

### Variables d'environnement principales

| Variable | Defaut | Description |
|----------|--------|-------------|
| `MEILI_MASTER_KEY` | - | Cle API Meilisearch (obligatoire) |
| `MEILI_URL` | `http://meilisearch:7700` | URL de Meilisearch |
| `QDRANT_URL` | `http://qdrant:6333` | URL de Qdrant |
| `INDEX_NAME` | `docs` | Nom de l'index partage |
| `EMBED_MODEL` | `intfloat/multilingual-e5-base` | Modele d'embeddings |
| `RERANK_MODEL` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Modele de reranking |
| `TOP_K` | `5` | Nombre de resultats finaux |
| `RRF_K` | `60` | Constante RRF (plus faible = plus de poids aux premiers) |
| `MIN_SCORE_THRESHOLD` | `0.1` | Score minimum de pertinence (0-1) |
| `SEARCH_MULTIPLIER` | `5` | Multiplicateur de recherche avant fusion |
| `CORS_ORIGINS` | `http://localhost:5173` | Origines CORS autorisees |

### Ingestion

| Variable | Defaut | Description |
|----------|--------|-------------|
| `DOCS_DIR` | `/workdir/data/docs` | Repertoire des documents sources |
| `CHUNK_SIZE` | `350` | Taille des chunks (caracteres) |
| `CHUNK_OVERLAP` | `100` | Overlap entre chunks |

### LLM (optionnel)

| Variable | Defaut | Description |
|----------|--------|-------------|
| `LLM_MODEL_PATH` | - | Chemin du modele GGUF |
| `LLM_N_CTX` | `8192` | Taille de la fenetre de contexte |
| `LLM_N_THREADS` | `0` | Nombre de threads (0 = auto) |
| `LLM_GPU_LAYERS` | `0` | Couches GPU (0 = CPU uniquement) |
| `LLM_TEMPERATURE` | `0.7` | Temperature de generation |
| `LLM_MAX_TOKENS` | `1024` | Tokens maximum par reponse |
| `LLM_MAX_HISTORY` | `5` | Profondeur de l'historique de conversation |

## API

### Endpoints principaux

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/ask` | POST | Recherche hybride (sans LLM) |
| `/chat` | POST | Chat conversationnel avec streaming SSE |
| `/chat/new` | POST | Creer une nouvelle session |
| `/chat/{id}` | GET | Recuperer une conversation |

### Health checks

| Endpoint | Description |
|----------|-------------|
| `/health` | Verification basique |
| `/health/live` | Sonde liveness (Kubernetes) |
| `/health/ready` | Sonde readiness |
| `/health/deep` | Diagnostic detaille de chaque composant |
| `/metrics` | Metriques Prometheus |

### Exemple de requete

**POST /ask**
```json
{
  "query": "Comment fonctionne l'encaisseuse SP2322 ?",
  "limit": 5
}
```

**Reponse :**
```json
{
  "answer": "Voici les informations trouvees dans vos documents :",
  "excerpts": [
    {
      "content": "L'encaisseuse **SP2322** est une machine...",
      "source": {
        "title": "Manuel_SP2322",
        "page": 12,
        "path": "...",
        "score": 0.85
      },
      "relevance_score": 85.0
    }
  ],
  "sources": ["Manuel_SP2322.pdf (p. 12)"],
  "total_results": 5
}
```

## Maintenance

### Reindexation
```bash
docker compose --profile ingestor run --rm ingestor
```

### Nettoyage complet des index
```bash
docker compose down
rm -rf data/indexes/meili/*
rm -rf data/indexes/qdrant/*
docker compose up -d
```

### Logs
```bash
docker compose logs -f api
docker compose logs -f frontend
```

## Developpement local (sans Docker)

```bash
# Frontend
cd frontend && npm install && npm run dev

# API
cd api && uv sync && uv run api

# Ingestor
cd ingest && uv sync && uv run ingest
```

## Depannage

| Probleme | Solution |
|----------|----------|
| "No results found" | Verifier que les documents sont dans `./data/docs/` et que l'indexation est terminee |
| "Error 503" | Verifier que Meilisearch et Qdrant sont demarres : `docker compose ps` |
| "CORS error" | Verifier `CORS_ORIGINS` dans `.env` |
| Resultats peu pertinents | Augmenter `MIN_SCORE_THRESHOLD`, reduire `RRF_K` ou `CHUNK_SIZE` |
| LLM ne repond pas | Verifier que `LLM_MODEL_PATH` pointe vers un fichier GGUF valide dans `./data/models/` |

## Securite

- Conteneurs non-root avec `no-new-privileges`
- CORS configure avec origines specifiques
- Validation Pydantic sur tous les inputs
- Fichiers temporaires en tmpfs
- Health checks Docker pour redemarrage automatique