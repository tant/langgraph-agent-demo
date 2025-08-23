import os
import logging
import uuid
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
try:
    # Prefer sse-starlette if installed for robust SSE handling
    from sse_starlette.sse import EventSourceResponse
except Exception:
    # Fallback: if not installed, disable EventSourceResponse (will use StreamingResponse)
    EventSourceResponse = None
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from agent.database import init_db, create_conversation, get_conversation, create_message, get_messages_history
from agent.langgraph_flow import AgentState, create_flow
from agent.retriever import upsert_vectors

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
    user_id: str
    metadata: Optional[dict] = None

class CreateConversationResponse(BaseModel):
    id: str
    user_id: str
    created_at: datetime

class CreateMessageRequest(BaseModel):
    content: str
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

@app.post("/conversations/{conversation_id}/stream")
async def stream_message_endpoint(conversation_id: str, request: CreateMessageRequest, background_tasks: BackgroundTasks):
    """
    Create a new message and stream the assistant's response.
    """
    logger.info(f"Streaming message in conversation {conversation_id}")
    try:
        conv_uuid = uuid.UUID(conversation_id)
        conv = await get_conversation(conv_uuid)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # 1. Save user message and enqueue its embedding
        user_msg = await create_message(
            conversation_id=conv_uuid, sender="user", text=request.content
        )
        background_tasks.add_task(
            embed_and_store_message,
            message_id=str(user_msg.id),
            conversation_id=str(conv_uuid),
            user_id=conv.user_id,
            text=request.content,
        )
        logger.info(f"User message {user_msg.id} saved.")

        # 2. Prepare the generator for the streaming response
        async def response_generator():
            full_response = ""
            try:
                # Get history for the flow state
                history = await get_messages_history(conv_uuid)
                initial_state: AgentState = {
                    "conversation_id": str(conv_uuid),
                    "user_id": conv.user_id,
                    "chat_history": [{"role": msg.sender, "content": msg.text} for msg in history],
                    "metadata": {"conversation_id": str(conv_uuid), "user_id": conv.user_id},
                    "retrieved_context": None,
                    "response": None,
                    "stream": True,
                    "intent": "unknown",
                    "intent_confidence": 0.0,
                    "need_retrieval_hint": False,
                    "clarify_questions": [],
                    "clarify_attempts": 0,
                }

                # We'll run the classify/retrieve nodes directly and then stream from
                # the streaming response node. This ensures per-chunk yields from
                # `generate_text_stream` are forwarded immediately to the SSE client.
                from agent.langgraph_flow import (
                    classify_node,
                    retrieve_node,
                    stream_respond_node,
                )

                logger.info(f"[{conversation_id}] Running classify/retrieve then streaming node directly")

                # Emit an initial debug SSE payload so clients can detect the open stream
                initial_payload = json.dumps({"debug": "stream-open"})
                init_sse = f"data: {initial_payload}\n\n"
                logger.info(f"[{conversation_id}] Yielding initial debug SSE: {init_sse.strip()}")
                yield init_sse
                # allow the event loop and server to flush this chunk
                await asyncio.sleep(0)

                # Run classifier node to decide if we should retrieve
                try:
                    classify_out = await classify_node(initial_state)
                    logger.info(f"[{conversation_id}] classify_out={classify_out}")
                except Exception as e:
                    logger.error(f"[{conversation_id}] classify_node failed: {e}", exc_info=True)
                    classify_out = {"need_retrieval": False}

                # Optionally run retrieve node
                try:
                    # Clarify/farewell handling
                    if classify_out.get("should_farewell"):
                        farewell = (
                            "Hiện mình chưa đủ thông tin để hỗ trợ chính xác. Bạn có thể quay lại khi sẵn sàng chia sẻ thêm nhé. Cảm ơn bạn!"
                        )
                        payload = json.dumps({"chunk": farewell})
                        yield f"data: {payload}\n\n"
                        await asyncio.sleep(0)
                        return

                    if classify_out.get("clarify_needed") and (int(classify_out.get("clarify_attempts", 0)) < 3):
                        # Stream the first clarify question and end this turn
                        questions_val = classify_out.get("clarify_questions")
                        questions = questions_val if isinstance(questions_val, list) else []
                        if questions and isinstance(questions[0], str):
                            cq = questions[0]
                            payload = json.dumps({"chunk": cq})
                            yield f"data: {payload}\n\n"
                            await asyncio.sleep(0)
                            return

                    if classify_out.get("need_retrieval"):
                        await retrieve_node(initial_state)
                        logger.info(f"[{conversation_id}] retrieve populated state.retrieved_context")
                except Exception as e:
                    logger.error(f"[{conversation_id}] retrieve_node failed: {e}", exc_info=True)

                # Stream directly from the streaming node
                chunk_index = 0
                try:
                    async for chunk in stream_respond_node(initial_state):
                        # chunk is expected to be a dict like {'response': '...'} or a string
                        logger.info(f"[{conversation_id}] streaming node yielded: {chunk!r}")
                        # Normalize
                        response_chunk = None
                        if isinstance(chunk, dict) and "response" in chunk:
                            response_chunk = chunk["response"]
                        elif isinstance(chunk, str):
                            response_chunk = chunk

                        if response_chunk is None:
                            logger.info(f"[{conversation_id}] streaming node yielded non-response: {chunk!r}")
                            continue

                        try:
                            payload = json.dumps({"chunk": response_chunk})
                        except Exception:
                            payload = json.dumps({"chunk": str(response_chunk)})
                        sse_data = f"data: {payload}\n\n"
                        logger.info(f"[{conversation_id}] Yielding chunk {chunk_index}: {sse_data.strip()}")
                        yield sse_data
                        # give the event loop a chance to schedule IO/flush
                        await asyncio.sleep(0)
                        full_response += response_chunk
                        chunk_index += 1
                except Exception as e:
                    logger.error(f"[{conversation_id}] Error in streaming node: {e}", exc_info=True)
            
            except Exception as e:
                logger.error(f"[{conversation_id}] Error during stream generation: {e}", exc_info=True)
            finally:
                logger.info(f"[{conversation_id}] Stream finished. Saving full assistant response.")
                if full_response:
                    # Save the complete assistant message
                    assistant_msg = await create_message(
                        conversation_id=conv_uuid, sender="assistant", text=full_response
                    )
                    # Enqueue embedding for the assistant's message
                    await embed_and_store_message(
                        message_id=str(assistant_msg.id),
                        conversation_id=str(conv_uuid),
                        user_id=conv.user_id,
                        text=full_response,
                    )
                    logger.info(f"Assistant message {assistant_msg.id} saved and embedding enqueued.")

        # Use EventSourceResponse if available for better SSE semantics and flushing
        if EventSourceResponse is not None:
            return EventSourceResponse(response_generator())
        else:
            # Fallback to StreamingResponse if no EventSourceResponse available
            from fastapi.responses import StreamingResponse
            return StreamingResponse(response_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error in stream endpoint: {e}", exc_info=True)
        # If we hit an import-time or startup error before streaming begins,
        # respond with a JSON error. We avoid StreamingResponse here because
        # StreamingResponse may not be imported in all branches.
        return JSONResponse(status_code=500, content={"detail": f"Error: {e}"})


async def run_assistant_flow(conversation_id: uuid.UUID, user_id: str):
    """
    Runs the LangGraph flow to generate and save the assistant's response.
    This is run in the background.
    """
    logger.info(f"Starting assistant flow for conversation {conversation_id}")
    try:
        # 1. Get history to build the current state
        history = await get_messages_history(conversation_id)
        
        # 2. Create initial state for the flow
        initial_state: AgentState = {
            "conversation_id": str(conversation_id),
            "user_id": user_id,
            "chat_history": [
                {"role": msg.sender, "content": msg.text} for msg in history
            ],
            "metadata": {
                "conversation_id": str(conversation_id),
                "user_id": user_id,
            },
            "retrieved_context": None,
            "response": None,
            "stream": False,
            "intent": "unknown",
            "intent_confidence": 0.0,
            "need_retrieval_hint": False,
            "clarify_questions": [],
            "clarify_attempts": 0,
        }

        # 3. Create and invoke the LangGraph flow
        flow = create_flow()
        final_state = await flow.ainvoke(initial_state)

        # 4. Save the assistant's response to the database
        assistant_response = final_state.get("response")
        if assistant_response:
            assistant_msg = await create_message(
                conversation_id=conversation_id,
                sender="assistant",
                text=assistant_response,
            )
            logger.info(f"Assistant response saved for conversation {conversation_id}")
            
            # Also embed the assistant's response
            background_tasks = BackgroundTasks()
            background_tasks.add_task(
                embed_and_store_message,
                message_id=str(assistant_msg.id),
                conversation_id=str(conversation_id),
                user_id=user_id,
                text=assistant_response,
            )
        else:
            logger.warning(f"No response generated by the flow for conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error in assistant flow for conversation {conversation_id}: {e}", exc_info=True)


async def embed_and_store_message(message_id: str, conversation_id: str, user_id: str, text: str):
    """
    Generates embedding for a message and stores it in ChromaDB.
    This is run in the background.
    """
    logger.info(f"Starting embedding for message {message_id}")
    try:
        # For now, we treat the whole message as a single document.
        # In the future, we might chunk it.
        documents = [text]
        metadatas = [{
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }]
        ids = [message_id]

        # Upsert into ChromaDB
        upsert_vectors(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"Successfully embedded and stored message {message_id}")

    except Exception as e:
        logger.error(f"Error embedding message {message_id}: {e}", exc_info=True)


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
        
        # Enqueue embedding for the user's message
        background_tasks.add_task(
            embed_and_store_message,
            message_id=str(msg.id),
            conversation_id=str(conv_uuid),
            user_id=conv.user_id,
            text=request.content,
        )

        # Enqueue the assistant flow to run in the background
        background_tasks.add_task(run_assistant_flow, conversation_id=conv_uuid, user_id=conv.user_id)
        
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