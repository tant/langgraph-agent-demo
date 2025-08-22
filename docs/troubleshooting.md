# Troubleshooting Guide

This document provides solutions to common issues you might encounter while setting up and running the Mai-Sale chat application.

## Ollama Issues

### Ollama is not running
**Problem:** Commands fail with "Connection refused" or "Ollama UNREACHABLE".
**Solution:**
1. Ensure Ollama daemon is running:
   ```bash
   # On Linux/macOS
   ollama serve
   
   # Or check if it's running as a service
   systemctl status ollama
   ```
2. Check Ollama status:
   ```bash
   uv run scripts/check_ollama.py --probe
   ```

### Required models are missing
**Problem:** Commands fail with "model not found" or the check script reports missing models.
**Solution:**
1. Pull the required models:
   ```bash
   ollama pull gpt-oss
   ollama pull bge-m3
   ```
2. Verify models are installed:
   ```bash
   ollama ls
   uv run scripts/check_ollama.py --probe
   ```

### Model generation/embedding fails
**Problem:** Generating responses or embeddings fails with timeout or other errors.
**Solution:**
1. Check if the model is responding:
   ```bash
   # Test generation
   curl http://localhost:11434/api/generate -d '{"model": "gpt-oss", "prompt": "hello"}'
   
   # Test embedding
   curl http://localhost:11434/api/embeddings -d '{"model": "bge-m3", "prompt": "hello"}'
   ```
2. Restart Ollama if needed:
   ```bash
   sudo systemctl restart ollama
   ```

## ChromaDB Issues

### ChromaDB path permission errors
**Problem:** ChromaDB fails to initialize with permission errors.
**Solution:**
1. Ensure the `database/chroma_db/` directory exists and is writable:
   ```bash
   mkdir -p database/chroma_db
   chmod 755 database/chroma_db
   ```
2. Check if another process is locking the database.

### ChromaDB query errors
**Problem:** Queries to ChromaDB fail with "where clause" or other errors.
**Solution:**
1. Ensure you're using the correct filter syntax. For multiple filters, use `$and`:
   ```python
   # Correct
   where={"$and": [{"conversation_id": "abc"}, {"user_id": "xyz"}]}
   
   # Incorrect for multiple filters
   where={"conversation_id": "abc", "user_id": "xyz"}
   ```

## SQLite Issues

### Database locked errors
**Problem:** SQLite database is locked by another process.
**Solution:**
1. Ensure only one instance of the application is running.
2. If using a file-based SQLite database, check if another process has a lock on the file.
3. Consider using an in-memory database for development:
   ```bash
   export DATABASE_URL="sqlite:///:memory:"
   ```

### Migration errors
**Problem:** Database schema issues after updates.
**Solution:**
1. For development, you can delete the database file to start fresh:
   ```bash
   rm database/sqlite.db
   ```
   The application will recreate the schema on next startup.

## FastAPI/Backend Issues

### Module not found errors
**Problem:** Python modules are not found when running the application.
**Solution:**
1. Ensure you're using `uv run` to run the application:
   ```bash
   uv run uvicorn agent.main:app --host 0.0.0.0 --port 8000
   ```
2. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

### CORS errors in browser
**Problem:** The Gradio UI cannot communicate with the backend due to CORS issues.
**Solution:**
1. Ensure the backend is configured to allow requests from the UI origin.
2. The default CORS configuration in `agent/main.py` allows all origins for development:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # For dev only
       # ...
   )
   ```
   In production, restrict this to specific origins.

## Gradio UI Issues

### UI not loading
**Problem:** The Gradio UI doesn't load in the browser.
**Solution:**
1. Ensure the UI is running:
   ```bash
   uv run --with gradio ui/gradio_app.py
   ```
2. Check the console output for errors.
3. Ensure the backend API is running and accessible.

### API calls from UI fail
**Problem:** The UI shows "Error sending message" or similar.
**Solution:**
1. Check the browser's developer console for specific error messages.
2. Ensure the API Base URL and API Key in the UI are correct.
3. Verify the backend is running and accessible from the UI's network.

## General Development Issues

### uv command not found
**Problem:** `uv` command is not available.
**Solution:**
1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Add uv to your PATH if needed.

### Python version issues
**Problem:** Dependency conflicts or compatibility issues.
**Solution:**
1. Ensure you're using Python 3.10 or higher.
2. Use uv to manage Python versions:
   ```bash
   uv python install 3.12
   ```

## Testing Issues

### Tests fail due to database connections
**Problem:** Unit tests fail with database connection errors.
**Solution:**
1. For unit tests, external dependencies like databases should be mocked.
2. For integration tests, ensure the test database is properly configured and accessible.

### Integration tests fail due to backend not running
**Problem:** Integration tests fail because the backend is not running.
**Solution:**
1. Ensure the backend is started before running integration tests:
   ```bash
   uv run uvicorn agent.main:app --host 0.0.0.0 --port 8000 &
   # Run tests
   uv run pytest tests/test_integration.py
   ```

## Performance Issues

### Slow API responses
**Problem:** API responses are slower than expected.
**Solution:**
1. Check if Ollama is running efficiently.
2. Ensure ChromaDB is not I/O bound.
3. For development, consider disabling synchronous embedding computation if not needed.

If you encounter issues not covered in this guide, please check the logs for more detailed error messages and consult the relevant documentation for the specific component (FastAPI, Ollama, ChromaDB, etc.).