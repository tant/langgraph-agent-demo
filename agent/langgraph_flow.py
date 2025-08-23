"""
LangGraph flow for the Mai-Sale chat application.

This module defines the basic LangGraph flow with three nodes:
- classify: Determine if retrieval is needed
- retrieve: Query ChromaDB for context
- respond: Build prompt and generate response using LLM
"""

from typing import Annotated, List, Dict, Any, Optional, Generator, AsyncGenerator
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
import uuid
import logging
from agent.database import get_messages_history
from agent.retriever import query_vectors, simple_rerank
from agent.ollama_client import generate_text, generate_text_stream

logger = logging.getLogger(__name__)

# --- State ---
class AgentState(TypedDict):
    """State for the LangGraph agent."""
    conversation_id: str
    user_id: str
    chat_history: Annotated[List[Dict[str, Any]], add_messages]  # List of message dicts with 'role' and 'content'
    metadata: Dict[str, Any]  # Additional metadata
    retrieved_context: Optional[List[Dict[str, Any]]]  # Retrieved context from ChromaDB
    response: Optional[str]  # Final response from the LLM
    stream: bool


async def classify_node(state: AgentState) -> Dict[str, Any]:
    """
    Simple classifier node: decide whether to perform retrieval based on the
    latest user message length or keywords. Returns a small dict indicating
    whether retrieval is needed.
    """
    logger.info("Classify node: Deciding if retrieval is necessary")
    need_retrieval = False
    try:
        latest = None
        for msg in reversed(state.get("chat_history", [])):
            if isinstance(msg, dict) and msg.get("role") == "user":
                latest = msg.get("content")
                break
        if latest:
            # simple heuristic: if message length > 30 or contains keyword
            if len(latest) > 30 or any(k in latest.lower() for k in ("who", "what", "why", "how", "google", "chip")):
                need_retrieval = True
    except Exception:
        logger.exception("Classify node: failed to inspect chat history")

    return {"need_retrieval": need_retrieval}


def build_prompt(state: AgentState) -> str:
    """Build a simple prompt from chat history and retrieved context."""
    parts = []
    # include retrieved context first if present
    rc = state.get("retrieved_context") or []
    if rc:
        parts.append("Retrieved context:")
        for d in rc:
            parts.append(d.get("text") or d.get("content") or str(d))

    # Instruction: ask the model to be concise. This ensures both streaming and
    # non-streaming nodes produce short answers (approx ~5 sentences).
    parts.append("Instruction: Provide a concise answer in about 5 sentences. Be clear, direct, and avoid unnecessary details.")

    parts.append("Conversation:")
    for msg in state.get("chat_history", []):
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
        parts.append(f"{role}: {content}")

    parts.append("Assistant:")
    return "\n".join(parts)


# --- Nodes ---
async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve node: Query ChromaDB for context based on the user's latest message.
    """
    logger.info("Retrieve node: Querying ChromaDB for context")
    
    # Get the latest user message
    user_message = None
    for msg in reversed(state["chat_history"]):
        # Check if it's a HumanMessage or dict with role 'user'
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            user_message = msg
            break
            
    if not user_message:
        logger.warning("Retrieve node: No user message found in chat history")
        state["retrieved_context"] = []
        # Return the expected node output shape
        return {"documents": [], "user_message": None}
        
    # Query ChromaDB
    # Prepare a safe default so we always have the variable defined
    reranked_results = []
    try:
        # Get content from message (handle both dict and object)
        if isinstance(user_message, dict):
            query_text = user_message["content"]
        else:
            query_text = user_message.content
            
        # Filter by conversation_id and user_id if available in metadata
        filter_metadata = {}
        if "conversation_id" in state["metadata"]:
            filter_metadata["conversation_id"] = state["metadata"]["conversation_id"]
        if "user_id" in state["metadata"]:
            filter_metadata["user_id"] = state["metadata"]["user_id"]
            
        results = query_vectors(
            query_text=query_text,
            collection_name="conversations_dev",  # Use default collection for now
            top_k=3,
            filter_metadata=filter_metadata or None
        )
        
        # Re-rank results
        reranked_results = simple_rerank(results, query_metadata=state["metadata"])
        
        # Store in state
        state["retrieved_context"] = reranked_results
        logger.info(f"Retrieve node: Retrieved and re-ranked {len(reranked_results)} results")
        
    except Exception as e:
        logger.error(f"Retrieve node: Error querying ChromaDB: {e}")
        state["retrieved_context"] = []
        
    logger.info("---RETRIEVE NODE FINISHED---")
    # Ensure we return the documents we actually retrieved/re-ranked
    documents = reranked_results
    return {"documents": documents, "user_message": user_message}


async def respond_node(state: AgentState) -> Dict[str, str]:
    """
    Respond node: Build prompt and generate a complete response.
    """
    logger.info("Respond node: Generating complete response")
    try:
        prompt = build_prompt(state)
        logger.info(f"Respond node: Built prompt:\n{prompt}")

        response_text = generate_text(prompt, model="gpt-oss")
        state["response"] = response_text
        logger.info("Respond node: Generated response successfully")

    except Exception as e:
        logger.error(f"Respond node: Error generating response: {e}")
        state["response"] = "Sorry, I encountered an error."
        response_text = state["response"]

    logger.info("---RESPOND NODE FINISHED---")
    return {"response": response_text}


async def stream_respond_node(state: AgentState) -> AsyncGenerator[Dict[str, str], None]:
    """
    Generates a response stream from the Ollama client.
    """
    logger.info("Stream Respond node: Building prompt and streaming response")
    try:
        prompt = build_prompt(state)
        logger.info(f"Stream Respond node: Built prompt:\n{prompt}")
        
        # Use the streaming client
        full_response = ""
        async for chunk in generate_text_stream(prompt, model="gpt-oss"):
            if chunk:
                full_response += chunk
                logger.info(f"Node yielding chunk: '{chunk}'")
                yield {"response": chunk}
        
        # After the loop, LangGraph will have the full response in the state
        # No explicit return is needed for the final state if done via yielding
        
    except Exception as e:
        logger.error(f"Stream Respond node: Error generating response: {e}", exc_info=True)
        yield {"response": "Sorry, I encountered an error while streaming."}


# --- Flow Definition ---
def create_flow() -> Any:
    """
    Create the LangGraph flow.
    """
    logger.info("Creating LangGraph flow")
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("respond", respond_node)
    
    # Add edges
    workflow.add_edge("classify", "retrieve")
    workflow.add_edge("retrieve", "respond")
    workflow.add_edge("respond", END)
    
    # Set entry point
    workflow.set_entry_point("classify")
    
    # Compile the graph
    app = workflow.compile()
    logger.info("LangGraph flow created successfully")
    return app

def create_streaming_flow() -> Any:
    """
    Create a LangGraph flow that supports streaming.
    """
    logger.info("Creating LangGraph streaming flow")
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("respond_stream", stream_respond_node) # Use the streaming node
    
    workflow.add_edge("classify", "retrieve")
    workflow.add_edge("retrieve", "respond_stream")
    workflow.add_edge("respond_stream", END)
    
    workflow.set_entry_point("classify")
    
    app = workflow.compile()
    logger.info("LangGraph streaming flow created successfully")
    return app


# --- Test function ---
async def test_flow():
    """Test the LangGraph flow with a simple example."""
    # Create a test state
    test_state: AgentState = {
        "conversation_id": "test-conversation-id",
        "user_id": "test-user-id",
        "chat_history": [
            {"role": "user", "content": "Hello, I'm looking for information about Pixel phones."},
            {"role": "assistant", "content": "Hi there! I can help you with information about Pixel phones. What would you like to know?"}
        ],
        "metadata": {
            "conversation_id": "test-conversation-id",
            "user_id": "test-user-id"
        },
        "retrieved_context": None,
        "response": None
    }
    # Required by the AgentState TypedDict
    test_state["stream"] = False
    
    print("Testing LangGraph flow...")
    print(f"Initial state: {test_state}")
    
    # Create and run the flow
    app = create_flow()
    # The compiled graph exposes async invocation methods; cast to Any for type checkers
    app_any = app  # type: Any
    final_state = await app_any.ainvoke(test_state)
    
    print(f"Final state: {final_state}")
    print(f"Response: {final_state['response']}")
    return final_state