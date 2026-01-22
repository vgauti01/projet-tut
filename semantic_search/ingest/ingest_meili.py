
import os
import re
from pathlib import Path
import json
import requests
from tqdm import tqdm
from settings import MEILI_URL, MEILI_MASTER_KEY, INDEX_NAME, DOCS_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from pdf_utils import extract_pages, chunk_text

def ensure_index():
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=headers)
    if r.status_code == 200:
        return
    # create index with primaryKey
    r = requests.post(f"{MEILI_URL}/indexes",
                      headers=headers,
                      json={"uid": INDEX_NAME, "primaryKey": "id"})
    r.raise_for_status()
    # set searchable/sortable/stop-words etc if needed
    requests.patch(f"{MEILI_URL}/indexes/{INDEX_NAME}/settings",
                   headers=headers,
                   json={
                       "searchableAttributes": ["content", "title", "path"],
                       "filterableAttributes": ["title", "path", "page"],
                       "sortableAttributes": [],
                       "displayedAttributes": ["content","title","path","page","chunk_id"]
                   })

def ingest_pdfs():
    headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
    docs_dir = Path(DOCS_DIR)
    pdfs = list(docs_dir.glob("**/*.pdf"))
    if not pdfs:
        print(f"Aucun PDF trouvé dans {docs_dir.resolve()}")
        return

    print(f"PDF trouvés: {len(pdfs)}")
    batch = []
    for pdf in tqdm(pdfs):
        title = pdf.stem
        for page_num, text in extract_pages(pdf):
            if not text.strip():
                continue
            for idx, chunk in enumerate(chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
                # Meilisearch IDs must be alphanumeric
                clean_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', pdf.name)
                doc = {
                    "id": f"{clean_filename}_{page_num}_{idx}",
                    "title": title,
                    "path": str(pdf),
                    "page": page_num,
                    "chunk_id": idx,
                    "content": chunk
                }
                batch.append(doc)
                if len(batch) >= 1000:
                    push_batch(batch, headers)
                    batch = []
    if batch:
        push_batch(batch, headers)

def push_batch(batch, headers):
    r = requests.post(f"{MEILI_URL}/indexes/{INDEX_NAME}/documents",
                      headers=headers, json=batch)
    r.raise_for_status()

if __name__ == "__main__":
    print("Initialisation de l'index…")
    ensure_index()
    print("Ingestion des PDF…")
    ingest_pdfs()
    print("Terminé ✅")
