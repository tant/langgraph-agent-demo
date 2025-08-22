"""
LangGraph flow for the Mai-Sale chat application.

This module defines the basic LangGraph flow with three nodes:
- classify: Determine if retrieval is needed
- retrieve: Query ChromaDB for context
- respond: Build prompt and generate response using LLM
"""

from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
import uuid
import logging
from agent.database import get_messages_history
from agent.retriever import query_vectors, simple_rerank
from agent.ollama_client import generate_text

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Agent State ---
class AgentState(TypedDict):
    """State for the LangGraph agent."""
    conversation_id: str
    user_id: str
    chat_history: Annotated[List[Dict[str, Any]], add_messages]  # List of message dicts with 'role' and 'content'
    metadata: Dict[str, Any]  # Additional metadata
    retrieved_context: Optional[List[Dict[str, Any]]]  # Retrieved context from ChromaDB
    response: Optional[str]  # Final response from the LLM

# --- Node Functions ---

async def classify_node(state: AgentState) -> AgentState:
    """
    Classify node: Determine if retrieval is needed based on the user's message and chat history.
    For simplicity in Phase 1, we'll always retrieve.
    In the future, this could be more sophisticated.
    """
    logger.info("Classify node: Determining if retrieval is needed")
    
    # For Phase 1, always retrieve
    # In a more advanced version, you might check:
    # - Keywords in the user's message
    # - Length of chat history
    # - Time since last retrieval
    # - Confidence of previous responses
    
    # Update state to indicate retrieval is needed
    state["metadata"]["retrieval_needed"] = True
    logger.info("Classify node: Retrieval is needed")
    return state

async def retrieve_node(state: AgentState) -> AgentState:
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
        return state
        
    # Query ChromaDB
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
        
    return state

async def respond_node(state: AgentState) -> AgentState:
    """
    Respond node: Build prompt with chat history and retrieved context, then generate response.
    """
    logger.info("Respond node: Building prompt and generating response")
    
    try:
        # Get the latest user message
        user_message = None
        for msg in reversed(state["chat_history"]):
            # Check if it's a HumanMessage or dict with role 'user'
            if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
                user_message = msg
                break
                
        if not user_message:
            raise ValueError("No user message found in chat history")
            
        # Build prompt
        prompt_parts = []
        
        # Add chat history (last few messages for context)
        # For simplicity, we'll add the last 3 messages
        history_messages = state["chat_history"][-3:]  # Last 3 messages
        if history_messages:
            prompt_parts.append("Conversation history:")
            for msg in history_messages:
                # Handle both dict and message objects
                if isinstance(msg, dict):
                    role = msg["role"]
                    content = msg["content"]
                elif isinstance(msg, HumanMessage):
                    role = "user"
                    content = msg.content
                elif isinstance(msg, AIMessage):
                    role = "assistant"
                    content = msg.content
                else:
                    # Fallback
                    role = "unknown"
                    content = str(msg)
                    
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")  # Empty line
            
        # Add retrieved context if available
        if state.get("retrieved_context"):
            prompt_parts.append("Relevant context:")
            for ctx in state["retrieved_context"][:2]:  # Use top 2 contexts
                doc = ctx["document"]
                prompt_parts.append(f"- {doc}")
            prompt_parts.append("")  # Empty line
            
        # Add user's message
        # Get content from message (handle both dict and object)
        if isinstance(user_message, dict):
            user_content = user_message["content"]
        else:
            user_content = user_message.content
        prompt_parts.append(f"User: {user_content}")
        prompt_parts.append("Assistant:")  # Prompt the assistant to respond
        
        prompt = "\n".join(prompt_parts)
        logger.info(f"Respond node: Built prompt:\n{prompt}")
        
        # Generate response using Ollama
        response_text = generate_text(prompt, model="gpt-oss")
        state["response"] = response_text
        logger.info("Respond node: Generated response successfully")
        
    except Exception as e:
        logger.error(f"Respond node: Error generating response: {e}")
        state["response"] = "Sorry, I encountered an error while generating a response."
        
    return state

# --- Flow Definition ---
def create_flow() -> StateGraph:
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
    
    print("Testing LangGraph flow...")
    print(f"Initial state: {test_state}")
    
    # Create and run the flow
    app = create_flow()
    final_state = await app.ainvoke(test_state)
    
    print(f"Final state: {final_state}")
    print(f"Response: {final_state['response']}")
    return final_state