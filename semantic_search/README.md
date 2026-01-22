# Assistant Documentaire Hybride (RAG System)

Système de recherche sémantique hybride combinant BM25 (Meilisearch) et recherche vectorielle (Qdrant) pour interroger efficacement vos documents PDF.

## 🚀 Fonctionnalités

- **Recherche hybride** : Combine la recherche par mots-clés (BM25) et la recherche sémantique (embeddings vectoriels)
- **Reciprocal Rank Fusion (RRF)** : Algorithme avancé de fusion des résultats pour une meilleure pertinence
- **Chunking intelligent** : Découpage des documents qui respecte les limites de phrases
- **Highlighting** : Mise en évidence des termes pertinents dans les résultats
- **Scores de pertinence** : Affichage visuel de la qualité des résultats
- **Interface moderne** : Frontend React avec Tailwind CSS et mode sombre

## 📋 Prérequis

- Docker et Docker Compose
- 4 GB de RAM minimum
- 2 GB d'espace disque

## 🛠️ Installation

1. **Cloner le projet**
```bash
cd semantic
```

2. **Configuration**
Créer un fichier `.env` à la racine :
```bash
MEILI_MASTER_KEY=votre-cle-securisee-ici
```

3. **Ajouter vos documents PDF**
Placer vos fichiers PDF dans le dossier `./data/docs/`

4. **Démarrer les services**
```bash
docker-compose up -d
```

5. **Indexation des documents**
L'indexation démarre automatiquement. Surveillez les logs :
```bash
docker-compose logs -f ingestor
```

6. **Accéder à l'interface**
Ouvrir http://localhost:5173 dans votre navigateur

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend      │  React + TypeScript + Tailwind
│  (port 5173)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API FastAPI   │  Fusion RRF + Scoring
│  (port 8000)    │
└────┬───────┬────┘
     │       │
     ▼       ▼
┌─────────┐ ┌─────────┐
│ Meili   │ │ Qdrant  │
│ (BM25)  │ │ (Vector)│
└─────────┘ └─────────┘
```

### Composants

- **Frontend** : Interface utilisateur en React
- **API** : Backend FastAPI qui orchestre les recherches
- **Meilisearch** : Moteur de recherche BM25 (mots-clés)
- **Qdrant** : Base de données vectorielle (recherche sémantique)
- **Ingestor** : Service d'indexation des PDFs

## ⚙️ Configuration Avancée

### Variables d'environnement de l'API

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MEILI_URL` | `http://meilisearch:7700` | URL de Meilisearch |
| `MEILI_MASTER_KEY` | - | Clé API Meilisearch (obligatoire) |
| `QDRANT_URL` | `http://qdrant:6333` | URL de Qdrant |
| `INDEX_NAME` | `docs` | Nom de l'index |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Modèle d'embeddings (384 dimensions) |
| `TOP_K` | `5` | Nombre de résultats à retourner |
| `RRF_K` | `60` | Constante RRF (plus faible = plus de poids aux premiers résultats) |
| `MIN_SCORE_THRESHOLD` | `0.01` | Score minimum pour filtrer les résultats |
| `SEARCH_MULTIPLIER` | `3` | Multiplier de recherche avant fusion |
| `CORS_ORIGINS` | `http://localhost:5173` | Origines CORS autorisées (séparées par des virgules) |

### Variables d'environnement de l'Ingestor

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DOCS_DIR` | `/workdir/data/docs` | Répertoire contenant les PDFs |
| `CHUNK_SIZE` | `800` | Taille des chunks en caractères |
| `CHUNK_OVERLAP` | `200` | Overlap entre chunks pour préserver le contexte |

## 🔍 Comment ça marche

### 1. Indexation
```
PDF → Extraction par pages → Chunking intelligent → Embeddings
                                      ↓
                        ┌─────────────┴─────────────┐
                        ↓                           ↓
                  Meilisearch (BM25)          Qdrant (Vector)
```

### 2. Recherche
```
Question utilisateur
        ↓
    Embeddings
        ↓
┌───────┴────────┐
↓                ↓
Meili (BM25)  Qdrant (Vector)
↓                ↓
└───────┬────────┘
        ↓
Reciprocal Rank Fusion (RRF)
        ↓
Filtrage par score minimum
        ↓
Formatting + Highlighting
        ↓
    Résultats
```

### 3. Reciprocal Rank Fusion (RRF)

Le RRF combine les résultats des deux moteurs de recherche :

```
Score(doc) = Σ (1 / (k + rank_i))
```

Où :
- `k` = constante (défaut: 60)
- `rank_i` = position du document dans chaque système de recherche

**Avantages** :
- Pas de normalisation de scores nécessaire
- Fonctionne bien même si les scores des systèmes sont sur des échelles différentes
- Favorise les documents bien classés dans plusieurs systèmes

## 📊 Optimisation de la Pertinence

### Chunking Intelligent
Le système découpe les documents en respectant :
1. Les limites de phrases (regex avancée)
2. Un overlap configurable pour préserver le contexte
3. Les phrases longues sont subdivisées intelligemment

### Extraction de Termes
- Filtrage des stop words (français + anglais)
- Termes de plus de 2 caractères
- Support des termes avec tirets et accents

### Highlighting
- Mise en évidence des termes pertinents avec `**terme**`
- Tri par longueur pour éviter les conflits
- Respect des limites de mots (`\b` regex)

## 🔧 Maintenance

### Réindexation
Pour réindexer les documents après modification :
```bash
docker-compose restart ingestor
```

### Nettoyage des index
```bash
# Arrêter les services
docker-compose down

# Supprimer les index
rm -rf data/indexes/meili/*
rm -rf data/indexes/qdrant/*

# Redémarrer
docker-compose up -d
```

### Logs
```bash
# API
docker-compose logs -f api

# Ingestor
docker-compose logs -f ingestor

# Tous les services
docker-compose logs -f
```

## 📈 Performances

### Temps de réponse typiques
- Recherche : 100-500ms
- Indexation : ~2-5 pages/seconde

### Consommation mémoire
- API : ~500 MB (avec modèle chargé)
- Meilisearch : ~200 MB
- Qdrant : ~300 MB
- Frontend : ~100 MB

## 🐛 Dépannage

### Problème : "No results found"
- Vérifier que les PDFs sont dans `./data/docs/`
- Vérifier les logs de l'ingestor : `docker-compose logs ingestor`
- Vérifier que l'indexation est terminée

### Problème : "Error 503"
- Vérifier que Meilisearch et Qdrant sont démarrés : `docker-compose ps`
- Vérifier les healthchecks : `docker-compose ps`

### Problème : "CORS error"
- Vérifier la configuration `CORS_ORIGINS` dans `compose.yml`
- S'assurer que l'URL du frontend correspond

### Problème : Résultats peu pertinents
- Ajuster `MIN_SCORE_THRESHOLD` (augmenter pour plus de filtrage)
- Ajuster `RRF_K` (diminuer pour favoriser les premiers résultats)
- Réduire `CHUNK_SIZE` pour des chunks plus précis
- Augmenter `CHUNK_OVERLAP` pour plus de contexte

## 📝 API Documentation

### `POST /ask`
Effectue une recherche hybride.

**Request:**
```json
{
  "query": "Comment fonctionne le nRF24L01?",
  "limit": 5
}
```

**Response:**
```json
{
  "answer": "Voici les informations trouvées dans vos documents :",
  "excerpts": [
    {
      "content": "Le **nRF24L01** est un module...",
      "source": {
        "title": "nRF24L01_Product_Specification",
        "page": 12,
        "path": "...",
        "score": 0.0234
      },
      "relevance_score": 78.5
    }
  ],
  "sources": ["nRF24L01_Product_Specification_v2_0.pdf (p. 12)"],
  "total_results": 5
}
```

### `GET /health`
Vérifie l'état de l'API.

**Response:**
```json
{
  "status": "ok"
}
```

## 🔐 Sécurité

- CORS configuré avec origines spécifiques
- Validation Pydantic sur tous les inputs
- Limites sur la taille des requêtes (1-1000 caractères)
- Limites sur le nombre de résultats (1-100)
- Gestion d'erreurs robuste avec HTTPException

## 🚧 Améliorations Futures

- [ ] Support de formats supplémentaires (DOCX, TXT, MD)
- [ ] Mise en cache des embeddings de requêtes
- [ ] Reranking avec cross-encoder
- [ ] Génération de réponses avec LLM
- [ ] Interface d'administration
- [ ] Métriques et monitoring (Prometheus)
- [ ] Tests automatisés
- [ ] CI/CD pipeline

## 📄 License

Ce projet est fourni à des fins éducatives et de démonstration.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.
