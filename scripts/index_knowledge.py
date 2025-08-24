# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "chromadb",
#   "requests",
#   "tqdm",
#   "python-dotenv",
# ]
# ///

"""
Script: index_knowledge.py
Purpose: Index all documents in the 'knowledge' folder into ChromaDB for agent retrieval.

- Reads all files in 'knowledge/'
- Splits content into chunks (200-512 tokens)
- Embeds using bge-m3 (via Ollama)
- Upserts into ChromaDB (local, ./database/chroma_db/)

Usage:
    uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev

Dependencies: chromadb, requests (for Ollama API), tqdm
"""

import os
import argparse
import time
import chromadb
from tqdm import tqdm
import requests
from dotenv import load_dotenv

# --- Config from .env.local ---
load_dotenv(".env.local")
OLLAMA_EMBEDDING_URL = os.environ.get("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 400))
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./database/chroma_db")
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "conversations_dev")

# --- Helpers ---
def chunk_text(text, chunk_size=CHUNK_SIZE):
    # Simple whitespace chunking (replace with tokenizer for better accuracy)
    words = text.split()
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i+chunk_size])
        yield chunk, len(words[i:i+chunk_size])

def get_embedding(text):
    payload = {"model": EMBEDDING_MODEL, "prompt": text}
    resp = requests.post(OLLAMA_EMBEDDING_URL, json=payload)
    resp.raise_for_status()
    return resp.json()["embedding"]

def index_file(filepath, collection, metadata_base, stats):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        doc_id = os.path.basename(filepath)
        for idx, (chunk, token_count) in enumerate(chunk_text(content)):
            embedding = get_embedding(chunk)
            meta = {"source": doc_id, "chunk": idx, **metadata_base}
            collection.add(
                ids=[f"{doc_id}#chunk_{idx}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[meta]
            )
            stats['chunks'] += 1
            stats['tokens'] += token_count
        stats['files'] += 1
    except Exception as e:
        stats['errors'].append((filepath, str(e)))


def main():
    parser = argparse.ArgumentParser(description="Index knowledge documents into ChromaDB.")
    parser.add_argument('--source', default='knowledge/', help='Folder with documents to index')
    parser.add_argument('--collection', default='conversations_dev', help='ChromaDB collection name')
    parser.add_argument('--clear', action='store_true', help='Clear collection before indexing')
    args = parser.parse_args()


    abs_chroma_path = os.path.abspath(CHROMA_PATH)
    print(f"[ChromaDB] Using persistent client at {abs_chroma_path}")
    os.makedirs(abs_chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=abs_chroma_path)

    collection = client.get_or_create_collection(args.collection)

    if args.clear:
        print(f"Clearing collection '{args.collection}'...")
        client.delete_collection(args.collection)
        collection = client.get_or_create_collection(args.collection)

    files = [os.path.join(args.source, f) for f in os.listdir(args.source) if os.path.isfile(os.path.join(args.source, f))]
    print(f"Indexing {len(files)} files from {args.source} into collection '{args.collection}'...")

    stats = {'files': 0, 'chunks': 0, 'tokens': 0, 'errors': []}
    start = time.time()
    for filepath in tqdm(files):
        index_file(filepath, collection, metadata_base={}, stats=stats)
    elapsed = time.time() - start

    # PersistentClient writes to disk automatically; no extra persist step required.

    print("\n--- Indexing Statistics ---")
    print(f"Files indexed:   {stats['files']}")
    print(f"Chunks created:  {stats['chunks']}")
    print(f"Tokens (approx): {stats['tokens']}")
    print(f"Elapsed time:    {elapsed:.2f} seconds")
    if stats['errors']:
        print(f"Errors: {len(stats['errors'])}")
        for f, err in stats['errors']:
            print(f"  {f}: {err}")
    else:
        print("No errors.")

if __name__ == "__main__":
    main()
