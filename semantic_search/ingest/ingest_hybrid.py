import os
import re
from pathlib import Path
import json
import requests
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from settings import MEILI_URL, MEILI_MASTER_KEY, INDEX_NAME, DOCS_DIR, CHUNK_SIZE, CHUNK_OVERLAP
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
from pdf_utils import extract_pages, chunk_text

model = SentenceTransformer(EMBED_MODEL)

def ensure_meili_index():
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers)
    if r.status_code == 404:
        r = requests.post(f"{MEILI_URL}/indexes",
                          headers=headers,
                          json={"uid": INDEX_NAME, "primaryKey": "id"})
        r.raise_for_status()
    
    requests.patch(f"{MEILI_URL}/indexes/{INDEX_NAME}/settings",
                   headers=headers,
                   json={
                       "searchableAttributes": ["content", "title", "path"],
                       "filterableAttributes": ["title", "path", "page"],
                       "displayedAttributes": ["content","title","path","page","chunk_id"]
                   })

def ensure_qdrant_collection():
    client = QdrantClient(url=QDRANT_URL)
    collections = client.get_collections().collections
    exists = any(c.name == INDEX_NAME for c in collections)
    if not exists:
        client.create_collection(
            collection_name=INDEX_NAME,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )

def ingest():
    ensure_meili_index()
    ensure_qdrant_collection()
    
    meili_headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    qdrant_client = QdrantClient(url=QDRANT_URL)
    
    docs_dir = Path(DOCS_DIR)
    pdfs = list(docs_dir.glob("**/*.pdf"))
    if not pdfs:
        print(f"Aucun PDF trouvé dans {docs_dir.resolve()}")
        return

    print(f"PDF trouvés: {len(pdfs)}")
    all_docs = []
    for pdf in tqdm(pdfs):
        title = pdf.stem
        for page_num, text in extract_pages(pdf):
            if not text.strip():
                continue
            for idx, chunk in enumerate(chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
                clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', pdf.name)
                doc_id = f"{clean_filename}_{page_num}_{idx}"
                doc = {
                    "id": doc_id,
                    "title": title,
                    "path": str(pdf),
                    "page": page_num,
                    "chunk_id": idx,
                    "content": chunk
                }
                all_docs.append(doc)

    print(f"Génération des embeddings pour {len(all_docs)} segments...")
    contents = [d["content"] for d in all_docs]
    embeddings = model.encode(contents, show_progress_bar=True)

    print("Indexation dans Meilisearch...")
    for i in range(0, len(all_docs), 100):
        batch = all_docs[i:i+100]
        r = requests.post(f"{MEILI_URL}/indexes/{INDEX_NAME}/documents",
                          headers=meili_headers, json=batch)
        r.raise_for_status()

    print("Indexation dans Qdrant...")
    points = []
    for i, doc in enumerate(all_docs):
        points.append(models.PointStruct(
            id=i, # Qdrant simple incremental ID or UUID
            vector=embeddings[i].tolist(),
            payload=doc
        ))
    
    for i in range(0, len(points), 100):
        qdrant_client.upsert(
            collection_name=INDEX_NAME,
            points=points[i:i+100]
        )
    
    print("Terminé ✅")

if __name__ == "__main__":
    ingest()
