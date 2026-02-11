import os
import re
from pathlib import Path
import json
import logging
import requests
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from .settings import MEILI_URL, MEILI_MASTER_KEY, INDEX_NAME, DOCS_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from .settings import EMBED_MODEL, QDRANT_URL
from .text_utils import chunk_text
from .extractors import get_extractor, supported_extensions
from .stopwords import FRENCH_STOP_WORDS

# Configuration du logging pour afficher les messages d'information et d'erreur avec un format de timestamp.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Chargement du modèle de génération d'embeddings à partir de la bibliothèque Sentence Transformers, en utilisant le nom du modèle spécifié dans les paramètres.
# Utilise HF_CACHE_DIR si défini pour charger depuis les modèles pré-téléchargés
import os
cache_dir = os.getenv("HF_CACHE_DIR")
logger.info(f"Cache directory: {cache_dir or 'default (~/.cache/huggingface)'}")
model = SentenceTransformer(EMBED_MODEL, cache_folder=cache_dir)

def ensure_meili_index():
    """ Vérifie si l'index Meilisearch existe, et le crée avec les paramètres appropriés s'il n'existe pas. """

    # Vérifie l'existence de l'index en envoyant une requête GET à l'API de Meilisearch.
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers)

    # Si l'index n'existe pas (code 404), le crée en envoyant une requête POST avec les paramètres de l'index.
    if r.status_code == 404:
        r = requests.post(f"{MEILI_URL}/indexes",
                          headers=headers,
                          json={"uid": INDEX_NAME, "primaryKey": "id"})
        # Si la création de l'index échoue, une exception est levée.
        r.raise_for_status()

    # Configure les paramètres de l'index pour définir les attributs recherchables, filtrables et affichés.
    # Note: Les stop words sont configurés mais s'appliquent uniquement lors de l'indexation.
    # La normalisation des requêtes côté API (search.py) complète cette configuration.
    requests.patch(f"{MEILI_URL}/indexes/{INDEX_NAME}/settings",
                   headers=headers,
                   json={
                       "searchableAttributes": ["content", "title", "path"],
                       "filterableAttributes": ["title", "path", "page", "source_type"],
                       "displayedAttributes": ["content", "title", "path", "page", "chunk_id", "source_type"],
                       "stopWords": FRENCH_STOP_WORDS
                   })

def ensure_qdrant_collection():
    """ Vérifie si la collection Qdrant existe, et la crée avec les paramètres appropriés si elle n'existe pas. """

    # Crée un client Qdrant et vérifie l'existence de la collection en récupérant la liste des collections existantes.
    client = QdrantClient(url=QDRANT_URL)
    collections = client.get_collections().collections
    exists = any(c.name == INDEX_NAME for c in collections)

    # Récupère la taille des vecteurs d'embeddings à partir du modèle de génération d'embeddings, pour configurer correctement la collection Qdrant.
    vector_size = model.get_sentence_embedding_dimension()
    
    # Si la collection n'existe pas, la crée en spécifiant le nom de la collection et la configuration des vecteurs (taille et type de distance).
    if not exists:
        client.create_collection(
            collection_name=INDEX_NAME,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

def ingest():
    """ Lance le processus d'ingestion des documents, incluant l'indexation dans Meilisearch et Qdrant. """

    # Vérifie et crée les index/collections nécessaires dans Meilisearch et Qdrant avant de commencer l'ingestion.
    ensure_meili_index()
    ensure_qdrant_collection()

    # Prépare les en-têtes d'authentification pour Meilisearch et crée un client pour Qdrant.
    meili_headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    qdrant_client = QdrantClient(url=QDRANT_URL)

    # Parcours le répertoire des documents pour collecter tous les fichiers supportés par les extracteurs disponibles.
    docs_dir = Path(DOCS_DIR)
    exts = supported_extensions()

    # Collecte tous les fichiers supportés
    files = []
    for ext in exts:
        files.extend(docs_dir.glob(f"**/*{ext}"))

    if not files:
        print(f"Aucun document trouvé dans {docs_dir.resolve()} (formats supportés: {', '.join(exts)})")
        return

    print(f"Documents trouvés: {len(files)}")
    all_docs = []
    # Parcours de chaque fichier trouvé pour extraire le texte, le découper en chunks, et préparer les documents à indexer.
    for file_path in tqdm(files, desc="Extraction"):
        extractor = get_extractor(file_path)
        if extractor is None:
            logger.warning(f"Pas d'extracteur pour {file_path}, ignoré")
            continue

        title = file_path.stem
        try:
            # Extraction du texte de chaque page du document à l'aide de l'extracteur approprié, puis découpage en chunks intelligents.
            for page in extractor.extract(file_path):
                # Vérifie que la page contient du texte non vide avant de continuer le traitement.
                if not page.text.strip():
                    continue

                # Récupère le type de source à partir des métadonnées de la page, ou utilise "unknown" si ce n'est pas disponible.
                source_type = page.metadata.get("source_type", "unknown")

                # Parcourt les chunks de texte extraits de la page, génère un ID unique pour chaque chunk en combinant le nom du fichier, le numéro de page et l'index du chunk, et prépare un document structuré avec les métadonnées associées.
                for idx, chunk in enumerate(chunk_text(page.text, CHUNK_SIZE, CHUNK_OVERLAP)):
                    clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', file_path.name)
                    doc_id = f"{clean_filename}_{page.page_number}_{idx}"
                    doc = {
                        "id": doc_id,
                        "title": title,
                        "path": str(file_path),
                        "page": page.page_number,
                        "chunk_id": idx,
                        "content": chunk,
                        "source_type": source_type,
                    }
                    all_docs.append(doc)
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de {file_path}: {e}")
            continue

    if not all_docs:
        print("Aucun segment extrait.")
        return

    print(f"Génération des embeddings pour {len(all_docs)} segments...")
    contents = [d["content"] for d in all_docs]
    # Génère les embeddings pour tous les segments de texte extraits en utilisant le modèle de génération d'embeddings
    # et affiche une barre de progression pendant le processus.
    embeddings = model.encode(contents, show_progress_bar=True)

    print("Indexation dans Meilisearch...")
    # Indexe les documents dans Meilisearch par lots de 100, en envoyant des requêtes POST à l'API de Meilisearch avec les documents à indexer.
    for i in range(0, len(all_docs), 100):
        batch = all_docs[i:i+100]
        r = requests.post(f"{MEILI_URL}/indexes/{INDEX_NAME}/documents",
                          headers=meili_headers, json=batch)
        r.raise_for_status()

    print("Indexation dans Qdrant...")
    # Prépare les points à insérer dans Qdrant en associant chaque document à son vecteur d'embedding.
    points = []
    for i, doc in enumerate(all_docs):
        points.append(models.PointStruct(
            id=i,
            vector=embeddings[i].tolist(),
            payload=doc
        ))

    # Insère les points dans Qdrant par lots de 100 en utilisant la méthode upsert du client Qdrant.
    for i in range(0, len(points), 100):
        qdrant_client.upsert(
            collection_name=INDEX_NAME,
            points=points[i:i+100]
        )

    print(f"Terminé! {len(all_docs)} segments indexés.")

if __name__ == "__main__":
    """ Point d'entrée principal pour l'ingestion des documents. Lorsque ce script est exécuté, il lance le processus d'ingestion """
    ingest()
