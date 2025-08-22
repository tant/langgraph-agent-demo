"""
Simple script to check the contents of the ChromaDB collection.
"""

import chromadb
import os

# Configuration
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./database/chroma_db/")
COLLECTION_NAME = "conversations_dev"

def main():
    print(f"Using ChromaDB path: {CHROMA_PATH}")
    
    # Create persistent client
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # List all collections
    collections = client.list_collections()
    print(f"Available collections: {[c.name for c in collections]}")
    
    # Check if our collection exists
    collection_names = [c.name for c in collections]
    if COLLECTION_NAME not in collection_names:
        print(f"Collection '{COLLECTION_NAME}' not found.")
        return
        
    # Get collection
    try:
        collection = client.get_collection(COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' exists.")
        
        # Get count of documents
        count = collection.count()
        print(f"Number of documents in collection: {count}")
        
        # Get a few documents
        if count > 0:
            results = collection.get(limit=5)
            print("\nSample documents:")
            # Handle case where results might be empty or have different structure
            if results and 'ids' in results and results['ids']:
                # Iterate through the results correctly
                for i in range(len(results['ids'])):
                    id = results['ids'][i]
                    doc = results['documents'][i] if results['documents'] and i < len(results['documents']) else ""
                    meta = results['metadatas'][i] if results['metadatas'] and i < len(results['metadatas']) else {}
                    print(f"  {i+1}. ID: {id}")
                    print(f"     Document: {doc[:100]}...")
                    print(f"     Metadata: {meta}")
                    print()
            else:
                print("  No documents retrieved or empty results.")
        else:
            print("No documents found in collection.")
            
    except Exception as e:
        print(f"Error accessing collection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()