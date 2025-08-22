# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
# ]
# ///
"""
Ollama client adapters for the Mai-Sale chat application.

This module provides adapters to interact with the Ollama API:
- generate: For text generation using gpt-oss model
- embeddings: For creating embeddings using bge-m3 model
"""

import os
import requests
from typing import List, Optional, Dict, Any
import logging

# --- Configuration ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", 11434))
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

# Default models
DEFAULT_GENERATE_MODEL = "gpt-oss"
DEFAULT_EMBEDDING_MODEL = "bge-m3"

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Adapter Functions ---

def generate_text(prompt: str, model: str = DEFAULT_GENERATE_MODEL, **kwargs) -> str:
    """
    Generate text using Ollama API.
    
    Args:
        prompt (str): The prompt to send to the model.
        model (str): The model to use for generation. Defaults to "gpt-oss".
        **kwargs: Additional parameters to pass to the API (e.g., options).
        
    Returns:
        str: The generated text response.
        
    Raises:
        requests.RequestException: If there's an error with the HTTP request.
        ValueError: If the response is invalid or missing expected fields.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # Ensure streaming is off for simple response
        **kwargs  # Allow additional options
    }
    
    logger.info(f"Calling Ollama generate API with model {model}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if "response" not in data:
            raise ValueError("Invalid response from Ollama API: missing 'response' field")
            
        logger.info("Successfully generated text with Ollama")
        return data["response"]
    except requests.RequestException as e:
        logger.error(f"Error calling Ollama generate API: {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid response from Ollama generate API: {e}")
        raise

def get_embedding(text: str, model: str = DEFAULT_EMBEDDING_MODEL) -> List[float]:
    """
    Get embeddings for text using Ollama API.
    
    Args:
        text (str): The text to embed.
        model (str): The model to use for embeddings. Defaults to "bge-m3".
        
    Returns:
        List[float]: The embedding vector.
        
    Raises:
        requests.RequestException: If there's an error with the HTTP request.
        ValueError: If the response is invalid or missing expected fields.
    """
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }
    
    logger.info(f"Calling Ollama embeddings API with model {model}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if "embedding" not in data:
            raise ValueError("Invalid response from Ollama API: missing 'embedding' field")
            
        embedding = data["embedding"]
        if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("Invalid response from Ollama API: 'embedding' is not a list of numbers")
            
        logger.info(f"Successfully generated embedding with Ollama (dimension: {len(embedding)})")
        return embedding
    except requests.RequestException as e:
        logger.error(f"Error calling Ollama embeddings API: {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid response from Ollama embeddings API: {e}")
        raise

# --- Test functions ---
def test_generate():
    """Test the generate_text function with a simple prompt."""
    try:
        response = generate_text("Say hello in Vietnamese", model=DEFAULT_GENERATE_MODEL)
        print(f"Generate test response: {response}")
        return response
    except Exception as e:
        print(f"Generate test failed: {e}")
        raise

def test_embedding():
    """Test the get_embedding function with a simple text."""
    try:
        embedding = get_embedding("Hello, this is a test sentence.", model=DEFAULT_EMBEDDING_MODEL)
        print(f"Embedding test: Got vector of length {len(embedding)}")
        # Check if it's a 1024-d vector as expected for bge-m3
        if len(embedding) != 1024:
            raise ValueError(f"Expected 1024-d vector, got {len(embedding)}-d")
        return embedding
    except Exception as e:
        print(f"Embedding test failed: {e}")
        raise