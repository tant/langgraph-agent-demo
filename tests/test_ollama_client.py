"""
Unit tests for the ollama_client module.
"""

import pytest
from unittest.mock import patch, MagicMock
from agent.ollama_client import generate_text, get_embedding

# --- Mock data ---
MOCK_GENERATE_RESPONSE = {
    "model": "gpt-oss",
    "response": "Hello! This is a test response from the mock Ollama API."
}

MOCK_EMBEDDING_RESPONSE = {
    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]  # Simplified 5-d vector for testing
}

def test_generate_text_success():
    """Test successful text generation with mocked API response."""
    with patch('agent.ollama_client.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_GENERATE_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = generate_text("Test prompt")
        assert result == MOCK_GENERATE_RESPONSE["response"]
        mock_post.assert_called_once()
        
def test_generate_text_http_error():
    """Test handling of HTTP errors from the API."""
    with patch('agent.ollama_client.requests.post') as mock_post:
        mock_post.side_effect = Exception("HTTP Error")
        
        with pytest.raises(Exception):
            generate_text("Test prompt")
            
def test_get_embedding_success():
    """Test successful embedding generation with mocked API response."""
    with patch('agent.ollama_client.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_EMBEDDING_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = get_embedding("Test text")
        assert result == MOCK_EMBEDDING_RESPONSE["embedding"]
        assert len(result) == 5  # Check dimension
        mock_post.assert_called_once()
        
def test_get_embedding_invalid_response():
    """Test handling of invalid API response."""
    with patch('agent.ollama_client.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"invalid": "response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError):
            get_embedding("Test text")