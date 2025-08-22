"""
Unit tests for the retriever module.
"""

import pytest
from unittest.mock import patch, MagicMock
from agent.retriever import query_vectors, simple_rerank

# --- Mock data ---
MOCK_QUERY_RESULTS = {
    'ids': [['doc1', 'doc2']],
    'documents': [['Document 1 content', 'Document 2 content']],
    'metadatas': [[{'source': 'source1', 'chunk': 0}, {'source': 'source2', 'chunk': 1}]],
    'distances': [[0.1, 0.5]]
}

def test_query_vectors_success():
    """Test successful vector query with mocked ChromaDB response."""
    with patch('agent.retriever.get_embedding') as mock_get_embedding, \
         patch('agent.retriever.get_or_create_collection') as mock_get_collection:
        
        # Mock embedding function
        mock_get_embedding.return_value = [0.1, 0.2, 0.3]
        
        # Mock collection and query response
        mock_collection = MagicMock()
        mock_collection.query.return_value = MOCK_QUERY_RESULTS
        mock_get_collection.return_value = mock_collection
        
        results = query_vectors("Test query")
        
        assert len(results) == 2
        assert results[0]['id'] == 'doc1'
        assert results[0]['document'] == 'Document 1 content'
        assert results[0]['distance'] == 0.1
        assert results[1]['id'] == 'doc2'
        assert results[1]['document'] == 'Document 2 content'
        assert results[1]['distance'] == 0.5
        
        mock_get_embedding.assert_called_once_with("Test query")
        mock_collection.query.assert_called_once()
        
def test_query_vectors_exception():
    """Test handling of exceptions during vector query."""
    with patch('agent.retriever.get_embedding') as mock_get_embedding:
        mock_get_embedding.side_effect = Exception("Embedding error")
        
        with pytest.raises(Exception):
            query_vectors("Test query")

def test_simple_rerank_no_results():
    """Test re-ranking with no results."""
    results = simple_rerank([])
    assert results == []

def test_simple_rerank_basic():
    """Test basic re-ranking by distance."""
    results = [
        {'id': 'doc1', 'document': 'Doc 1', 'metadata': {}, 'distance': 0.5},
        {'id': 'doc2', 'document': 'Doc 2', 'metadata': {}, 'distance': 0.1},  # Closer, should be ranked higher
        {'id': 'doc3', 'document': 'Doc 3', 'metadata': {}, 'distance': 0.3}
    ]
    
    reranked = simple_rerank(results)
    
    # Check that doc2 is now first (lowest distance)
    assert reranked[0]['id'] == 'doc2'
    assert reranked[1]['id'] == 'doc3'
    assert reranked[2]['id'] == 'doc1'

def test_simple_rerank_with_boost():
    """Test re-ranking with conversation boost."""
    results = [
        {'id': 'doc1', 'document': 'Doc 1', 'metadata': {'conversation_id': 'conv-a'}, 'distance': 0.5},
        {'id': 'doc2', 'document': 'Doc 2', 'metadata': {'conversation_id': 'conv-b'}, 'distance': 0.1},
        {'id': 'doc3', 'document': 'Doc 3', 'metadata': {'conversation_id': 'conv-a'}, 'distance': 0.3}  # Same conv, should be boosted
    ]
    
    query_metadata = {'conversation_id': 'conv-a'}
    reranked = simple_rerank(results, query_metadata)
    
    # Check the ranking based on the scoring logic:
    # doc3: -0.3 + 1.0 = 0.7 (highest)
    # doc1: -0.5 + 1.0 = 0.5 (second)
    # doc2: -0.1 + 0.0 = -0.1 (lowest)
    assert reranked[0]['id'] == 'doc3'
    assert reranked[1]['id'] == 'doc1'
    assert reranked[2]['id'] == 'doc2'