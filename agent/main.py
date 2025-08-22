import os
import logging
import uuid
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from agent.database import init_db, create_conversation, get_conversation, create_message, get_messages_history

# --- Configuration ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", 11434))
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./database/chroma_db")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite+aiosqlite:///./database/sqlite.db"
)  # Default to SQLite for dev
# For simplicity in Phase 1, we'll use a comma-separated list of valid keys from env
# In production, this should be replaced with a more secure method
X_API_KEYS = set(
    os.environ.get("X_API_KEYS", "default-dev-key").split(",")
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI(title="Mai-Sale Chat API", version="0.1.0")

# --- CORS ---
# Allow all for development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# --- Middleware for API Key Authentication ---
@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    """Middleware to check for valid X-API-Key header, except for /healthz and /version"""
    logger.info(f"Received request to {request.url.path}")
    
    # Skip auth for health and version endpoints
    if request.url.path in ["/healthz", "/version", "/ready"]:
        logger.info(f"Skipping auth for {request.url.path}")
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    logger.info(f"API Key from header: {api_key}")
    
    if not api_key or api_key not in X_API_KEYS:
        logger.warning(f"Unauthorized access attempt to {request.url.path} with key: {api_key}")
        # Return JSON response directly instead of raising HTTPException
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: Invalid or missing X-API-Key"}
        )
    # Optionally, you could attach the user_id or other info derived from the key to the request state
    # request.state.user_id = get_user_id_from_key(api_key)
    
    logger.info("API Key is valid, proceeding with request")
    response = await call_next(request)
    return response


# --- App Events ---
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized.")


# Pydantic models for request/response
class CreateConversationRequest(BaseModel):
    user_id: str = Field(..., example="user-123")
    metadata: Optional[dict] = None

class CreateConversationResponse(BaseModel):
    id: str
    user_id: str
    created_at: datetime

class CreateMessageRequest(BaseModel):
    content: str = Field(..., example="Hello, how can you help me?")
    metadata: Optional[dict] = None

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender: str  # 'user' or 'assistant'
    content: str
    created_at: datetime
    metadata: Optional[dict] = None

class ConversationHistoryResponse(BaseModel):
    messages: List[MessageResponse]
@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "ok"}

@app.get("/version")
async def get_version():
    """Get application version"""
    logger.info("Version requested")
    return {"version": app.version, "name": app.title}

@app.get("/ready")
async def ready_check():
    """Readiness check endpoint"""
    logger.info("Readiness check requested")
    
    # Check database connectivity
    db_ready = False
    try:
        from agent.database import engine
        # If we can import the engine, consider it ready for now
        # In a more robust implementation, you might want to do a real connectivity test
        db_ready = engine is not None
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
    
    # Check Ollama connectivity (simple ping)
    ollama_ready = False
    try:
        from agent.ollama_client import generate_text
        # Simple generate call to check if Ollama is responsive
        generate_text("ping", model="gpt-oss")
        ollama_ready = True
    except Exception as e:
        logger.error(f"Ollama readiness check failed: {e}")
    
    # Check ChromaDB connectivity
    chroma_ready = False
    try:
        from agent.retriever import chroma_client
        # Simple operation to check connectivity
        chroma_client.heartbeat()
        chroma_ready = True
    except Exception as e:
        logger.error(f"ChromaDB readiness check failed: {e}")
    
    if db_ready and ollama_ready and chroma_ready:
        return {"status": "ok", "details": {"database": "ok", "ollama": "ok", "chromadb": "ok"}}
    else:
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "not ready", 
                "details": {
                    "database": "ok" if db_ready else "error",
                    "ollama": "ok" if ollama_ready else "error", 
                    "chromadb": "ok" if chroma_ready else "error"
                }
            }
        )

# --- Main API Endpoints ---
@app.post("/conversations", response_model=CreateConversationResponse, status_code=201)
async def create_conversation_endpoint(request: CreateConversationRequest):
    """Create a new conversation"""
    logger.info(f"Creating conversation for user {request.user_id}")
    try:
        conv = await create_conversation(request.user_id, request.metadata)
        logger.info(f"Conversation created with ID {conv.id}")
        return CreateConversationResponse(
            id=str(conv.id),
            user_id=conv.user_id,
            created_at=conv.created_at
        )
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/conversations/{conversation_id}/messages", status_code=202)
async def create_message_endpoint(conversation_id: str, request: CreateMessageRequest, background_tasks: BackgroundTasks):
    """Create a new message in a conversation"""
    logger.info(f"Creating message in conversation {conversation_id}")
    try:
        # Validate conversation ID
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            logger.warning(f"Invalid conversation ID format: {conversation_id}")
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        # Check if conversation exists
        conv = await get_conversation(conv_uuid)
        if not conv:
            logger.warning(f"Conversation not found: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        # Create message (user message)
        msg = await create_message(
            conversation_id=conv_uuid,
            sender="user",
            text=request.content,
            metadata=request.metadata
        )
        logger.info(f"Message created with ID {msg.id}")
        
        # TODO: In future, enqueue embedding job here using background_tasks
        # For now, we just acknowledge the message creation
        
        # Return minimal response for fast ACK
        return {"message_id": str(msg.id), "status": "accepted"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history_endpoint(conversation_id: str):
    """Get the message history for a conversation"""
    logger.info(f"Getting history for conversation {conversation_id}")
    try:
        # Validate conversation ID
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            logger.warning(f"Invalid conversation ID format: {conversation_id}")
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        # Check if conversation exists
        conv = await get_conversation(conv_uuid)
        if not conv:
            logger.warning(f"Conversation not found: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        # Get messages
        messages = await get_messages_history(conv_uuid)
        logger.info(f"Retrieved {len(messages)} messages")
        
        # Convert to response model
        message_responses = [
            MessageResponse(
                id=str(msg.id),
                conversation_id=str(msg.conversation_id),
                sender=msg.sender,
                content=msg.text,
                created_at=msg.created_at,
                metadata=msg.metadata_
            )
            for msg in messages
        ]
        
        return ConversationHistoryResponse(messages=message_responses)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# --- Main Execution (for uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)