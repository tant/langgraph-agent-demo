"""
Config module for agent: load all environment variables and constants in one place.
Other modules should import from here instead of reading os.environ directly.
"""
import os
from dotenv import load_dotenv

# Load .env.local if present
load_dotenv(".env.local")

# Ollama endpoints
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_GENERATE_URL = os.environ.get("OLLAMA_GENERATE_URL", f"{OLLAMA_BASE_URL}/api/generate")
OLLAMA_EMBEDDING_URL = os.environ.get("OLLAMA_EMBEDDING_URL", f"{OLLAMA_BASE_URL}/api/embeddings")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", f"{OLLAMA_BASE_URL}/api/tags")

# Model names
GENERATE_MODEL = os.environ.get("GENERATE_MODEL", "gpt-oss")
REASONING_MODEL = os.environ.get("REASONING_MODEL", "gpt-oss")
SMALL_GENERATE_MODEL = os.environ.get("SMALL_GENERATE_MODEL", "phi4-mini")
SMALL_REASONING_MODEL = os.environ.get("SMALL_REASONING_MODEL", "phi4-mini-reasoning")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")

# ChromaDB
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./database/chroma_db")
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "conversations_dev")

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./database/sqlite.db")

# API keys
X_API_KEYS = set(os.environ.get("X_API_KEYS", "default-dev-key").split(","))

# Persona & intent
PERSONA_PATH = os.environ.get("PERSONA_PATH", "./prompts/system_persona_vi.md")
PERSONA_MAX_CHARS = int(os.environ.get("PERSONA_MAX_CHARS", 4000))
INTENT_CONFIDENCE_THRESHOLD = float(os.environ.get("INTENT_CONFIDENCE_THRESHOLD", 0.5))

# Chunking
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 400))
OVERLAP_SIZE = int(os.environ.get("OVERLAP_SIZE", 50))
