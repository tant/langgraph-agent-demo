"""
Retriever module for the Mai-Sale chat application.

This module provides functions to interact with ChromaDB for vector retrieval:
- Initialize PersistentClient with CHROMA_PATH
- Query vectors with filters and top-K selection
- Simple re-ranking based on scores and heuristics
"""

import os
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from typing import List, Dict, Any, Optional
import logging
from agent.ollama_client import get_embedding

# --- Configuration ---
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./database/chroma_db")
DEFAULT_TOP_K = 3
DEFAULT_COLLECTION_NAME = "conversations_dev"

# --- Logging ---
logger = logging.getLogger(__name__)

# --- ChromaDB Client ---
# Create persistent client
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

def get_or_create_collection(name: str = DEFAULT_COLLECTION_NAME):
    """Get or create a ChromaDB collection."""
    return chroma_client.get_or_create_collection(name)

# --- Retrieval Functions ---

def query_vectors(
    query_text: str,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    top_k: int = DEFAULT_TOP_K,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Query vectors from ChromaDB using text query.
    
    Args:
        query_text (str): The text to query with.
        collection_name (str): The name of the collection to query.
        top_k (int): Number of top results to return.
        filter_metadata (Optional[Dict]): Metadata filters to apply.
        
    Returns:
        List[Dict]: List of results with 'id', 'document', 'metadata', and 'distance'.
    """
    logger.info(f"Querying vectors from collection '{collection_name}' with top_k={top_k}")
    
    try:
        # Get embedding for query text
        query_embedding = get_embedding(query_text)
        
        # Get collection
        collection = get_or_create_collection(collection_name)
        
        # Query collection
        # ChromaDB requires $and operator for multiple filters
        chroma_where = None
        if filter_metadata:
            if len(filter_metadata) == 1:
                # Single filter, can use directly
                chroma_where = filter_metadata
            else:
                # Multiple filters, need to use $and
                chroma_where = {"$and": [{k: v} for k, v in filter_metadata.items()]}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=chroma_where,
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i],
            })
            
        logger.info(f"Retrieved {len(formatted_results)} results from ChromaDB")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error querying vectors from ChromaDB: {e}")
        raise

def simple_rerank(results: List[Dict[str, Any]], query_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Simple re-ranking of results based on distance and heuristics.
    
    Args:
        results (List[Dict]): List of results from query_vectors.
        query_metadata (Optional[Dict]): Metadata of the current query (e.g., conversation_id, user_id).
        
    Returns:
        List[Dict]: Re-ranked list of results.
    """
    if not results:
        return results
        
    logger.info(f"Re-ranking {len(results)} results")
    
    # For now, a simple re-ranking based on distance and same-conversation boost
    def rank_score(result: Dict[str, Any]) -> float:
        # Lower distance is better (closer vectors)
        base_score = -result['distance']  # Negative because lower distance is better
        
        # Boost score if it's from the same conversation
        if query_metadata and 'conversation_id' in query_metadata:
            if result['metadata'] and result['metadata'].get('conversation_id') == query_metadata['conversation_id']:
                base_score += 1.0  # Boost by 1.0 for same conversation
                
        # Boost score if it's from the same user
        if query_metadata and 'user_id' in query_metadata:
            if result['metadata'] and result['metadata'].get('user_id') == query_metadata['user_id']:
                base_score += 0.5  # Boost by 0.5 for same user
                
        return base_score
        
    # Sort results by rank score (descending)
    ranked_results = sorted(results, key=rank_score, reverse=True)
    logger.info("Re-ranking completed")
    return ranked_results

# --- Test functions ---
def test_query_and_rerank():
    """Test querying and re-ranking with a simple example."""
    try:
        # For testing, we'll use a generic query
        # In a real scenario, you would have indexed some documents first
        query_text = "What is the weather like today?"
        print(f"Querying with text: '{query_text}'")
        
        # Query vectors (this might return empty results if no data is indexed)
        results = query_vectors(query_text, top_k=5)
        print(f"Retrieved {len(results)} results")
        
        # Print raw results
        for i, result in enumerate(results):
            print(f"  {i+1}. ID: {result['id']}, Distance: {result['distance']:.4f}")
            print(f"     Document: {result['document'][:100]}...")
            print(f"     Metadata: {result['metadata']}")
            
        # Re-rank results
        reranked_results = simple_rerank(results, query_metadata={'conversation_id': 'test-conversation-id'})
        print(f"\nRe-ranked {len(reranked_results)} results")
        
        # Print re-ranked results
        for i, result in enumerate(reranked_results):
            print(f"  {i+1}. ID: {result['id']}, Distance: {result['distance']:.4f}")
            print(f"     Document: {result['document'][:100]}...")
            print(f"     Metadata: {result['metadata']}")
            
        return reranked_results
    except Exception as e:
        print(f"Query and re-rank test failed: {e}")
        raise