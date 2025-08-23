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
from typing import List, Optional, Dict, Any, AsyncGenerator
import pathlib


def _load_dotenv_simple(filename: str = ".env.local") -> None:
    """Lightweight dotenv loader: loads KEY=VALUE from file into os.environ if not set.

    Handles comment lines, fenced code blocks, and ${VAR} expansion using current os.environ.
    """
    # search current working dir and repo root (one level up from this file)
    candidates = [pathlib.Path.cwd() / filename, pathlib.Path(__file__).parent.parent / filename]
    for p in candidates:
        try:
            full = p.resolve()
            if not full.exists():
                continue
            with full.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or line.startswith("```"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    v = os.path.expandvars(v)
                    if k not in os.environ:
                        os.environ[k] = v
            return
        except Exception:
            return


# Load .env.local early so env-based config below picks up values
_load_dotenv_simple()
import logging
import json
import httpx

# --- Configuration ---
# Allow configuring Ollama endpoints via environment variables.
# Priority (highest -> lowest): specific URL env (e.g. OLLAMA_GENERATE_URL) -> OLLAMA_BASE_URL -> OLLAMA_HOST/OLLAMA_PORT
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", 11434))
_DEFAULT_BASE = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

# You can set a full base URL, or individual endpoint URLs for more control.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_BASE)
OLLAMA_GENERATE_URL = os.environ.get("OLLAMA_GENERATE_URL", f"{OLLAMA_BASE_URL}/api/generate")
OLLAMA_EMBEDDING_URL = os.environ.get("OLLAMA_EMBEDDING_URL", f"{OLLAMA_BASE_URL}/api/embeddings")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", f"{OLLAMA_BASE_URL}/api/tags")

# Default models
DEFAULT_GENERATE_MODEL = os.environ.get("DEFAULT_GENERATE_MODEL", "gpt-oss")
DEFAULT_EMBEDDING_MODEL = os.environ.get("DEFAULT_EMBEDDING_MODEL", "bge-m3")

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
    url = OLLAMA_GENERATE_URL
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        **kwargs,
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

async def generate_text_stream(prompt: str, model: str = "gpt-oss") -> AsyncGenerator[str, None]:
    """
    Generates text from a prompt using the Ollama API with streaming.
    """
    url = OLLAMA_GENERATE_URL
    data = {"model": model, "prompt": prompt, "stream": True}
    
    logger.info(f"Calling Ollama generate API with streaming for model {model}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=data) as response:
                response.raise_for_status()
                # Buffer text and parse line-delimited JSON or individual JSON objects
                buffer = ""
                async for text_chunk in response.aiter_text():
                    if not text_chunk:
                        continue
                    buffer += text_chunk
                    # Try to split by newlines which many streaming endpoints use
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            json_chunk = json.loads(line)
                            yield json_chunk.get("response", "")
                        except json.JSONDecodeError:
                            # If the line is not valid JSON, try to parse the accumulated buffer as JSON
                            try:
                                json_chunk = json.loads(line)
                                yield json_chunk.get("response", "")
                            except Exception:
                                # Give up on this line; yield raw fallback so UI can at least show text
                                yield line
                # After the stream finishes, try to parse any remaining buffer
                if buffer:
                    rem = buffer.strip()
                    if rem:
                        try:
                            json_chunk = json.loads(rem)
                            yield json_chunk.get("response", "")
                        except Exception:
                            yield rem
    except httpx.ReadTimeout:
        logger.error(f"Ollama request timed out after 60 seconds for model {model}.")
        yield "[ERROR: The request to the AI model timed out. The model might be busy or unavailable. Please try again later.]"
    except Exception as e:
        logger.error(f"An unexpected error occurred while streaming from Ollama: {e}", exc_info=True)
        yield f"[ERROR: An unexpected error occurred: {e}]"
    finally:
        logger.info("Ollama stream finished.")

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
    url = OLLAMA_EMBEDDING_URL
    payload = {"model": model, "prompt": text}
    
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


if __name__ == "__main__":
    # Simple local debug helper to print resolved Ollama URLs
    print("OLLAMA_BASE_URL:", OLLAMA_BASE_URL)
    print("OLLAMA_GENERATE_URL:", OLLAMA_GENERATE_URL)
    print("OLLAMA_EMBEDDING_URL:", OLLAMA_EMBEDDING_URL)
    print("OLLAMA_TAGS_URL:", OLLAMA_TAGS_URL)
    print("DEFAULT_GENERATE_MODEL:", DEFAULT_GENERATE_MODEL)
    print("DEFAULT_EMBEDDING_MODEL:", DEFAULT_EMBEDDING_MODEL)