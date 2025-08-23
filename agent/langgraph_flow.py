"""
LangGraph flow for the Mai-Sale chat application.

This module defines the basic LangGraph flow with three nodes:
- classify: Determine if retrieval is needed
- retrieve: Query ChromaDB for context
- respond: Build prompt and generate response using LLM
"""

from typing import Annotated, List, Dict, Any, Optional, AsyncGenerator
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage
import logging
from agent.retriever import query_vectors, simple_rerank
from agent.ollama_client import generate_text, generate_text_stream
import os
import pathlib

# --- Env-configurable knobs ---
INTENT_CONFIDENCE_THRESHOLD: float = float(os.environ.get("INTENT_CONFIDENCE_THRESHOLD", "0.5"))
PERSONA_MAX_CHARS: int = int(os.environ.get("PERSONA_MAX_CHARS", "4000"))

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
    # Intent & clarify
    intent: Optional[str]
    intent_confidence: Optional[float]
    need_retrieval_hint: Optional[bool]
    clarify_questions: Optional[List[str]]
    clarify_attempts: Optional[int]
    preferred_language: Optional[str]  # 'vi' (default) or 'en'


def _keyword_heuristic_intent(text: str) -> str:
    """Fallback heuristic for intent classification using bilingual keywords."""
    t = (text or "").lower()
    assemble_kw = [
        "lắp ráp", "ráp máy", "cấu hình", "tư vấn linh kiện", "tương thích", "bottleneck", "ngân sách",
        "tản nhiệt", "psu", "fps", "chơi game", "render", "build pc", "pc build", "spec",
        "compatibility", "budget", "cooler", "motherboard", "cpu", "gpu", "ssd", "case", "mini-itx",
        "micro-atx", "atx", "overclock", "bios", "driver", "photoshop", "premiere"
    ]
    shopping_kw = [
        "mua", "đặt", "giá", "bao nhiêu", "khuyến mãi", "giảm giá", "còn hàng", "hết hàng",
        "giao hàng", "vận chuyển", "thanh toán", "đổi trả", "màu", "phiên bản", "mẫu", "buy",
        "order", "price", "cost", "discount", "promotion", "in stock", "out of stock", "shipping",
        "delivery", "payment", "return", "refund", "sku", "model", "color"
    ]
    warranty_kw = [
        "bảo hành", "kiểm tra bảo hành", "chính sách", "thời hạn", "serial", "hóa đơn", "1 đổi 1",
        "doa", "trung tâm bảo hành", "quy trình", "warranty", "check warranty", "warranty policy",
        "duration", "sn", "invoice", "defect", "rma", "service center", "process"
    ]
    if any(k in t for k in assemble_kw):
        return "assemble_pc"
    if any(k in t for k in shopping_kw):
        return "shopping"
    if any(k in t for k in warranty_kw):
        return "warranty"
    return "unknown"


def _need_retrieval_for_intent(intent: str, latest_text: str) -> bool:
    if intent == "shopping":
        return True
    if intent == "warranty":
        # If asking general policy without specifics could be False, but default True
        return True
    if intent == "assemble_pc":
        # Default True as prices/compat often needed
        return True
    # unknown
    return False


async def classify_node(state: AgentState) -> Dict[str, Any]:
    """LLM-based intent detection with bilingual support and clarify suggestions."""
    logger.info("Classify node: Detecting intent and retrieval need")
    # Extract latest and a few recent user messages
    latest = None
    recents: List[str] = []
    for msg in reversed(state.get("chat_history", [])):
        if isinstance(msg, dict) and msg.get("role") == "user":
            if latest is None:
                content = msg.get("content")
                latest = content if isinstance(content, str) else ""
            else:
                content = msg.get("content")
                if isinstance(content, str) and content:
                    recents.append(content)
            if len(recents) >= 3:
                break

    # Detect preferred language based on the first user message in the conversation; default to VI
    def _detect_language_first_user(history: List[Dict[str, Any]]) -> str:
        try:
            # find first user message in chronological order
            for msg in history:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    text = msg.get("content")
                    if not isinstance(text, str):
                        break
                    t = text.lower()
                    # If contains Vietnamese diacritics, assume VI
                    if any(ch in t for ch in "àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"):
                        return "vi"
                    # Basic Vietnamese cue words
                    vi_words = ["anh", "em", "mình", "bạn", "không", "vâng", "dạ", "ạ", "nhé", "tư vấn", "giá", "mua"]
                    if any(w in t for w in vi_words):
                        return "vi"
                    # Basic English cue words (no diacritics)
                    en_words = ["hello", "hi", "please", "price", "buy", "warranty", "how", "what", "can you", "i want"]
                    if any(w in t for w in en_words):
                        return "en"
                    # Default to VI if unsure
                    return "vi"
        except Exception:
            pass
        return "vi"

    preferred_lang = state.get("preferred_language") or _detect_language_first_user(list(reversed(list(reversed(state.get("chat_history", []))))))
    state["preferred_language"] = preferred_lang

    # Build prompt
    from json import loads
    prompt = (
        "Bạn là bộ phân loại intent cho chat tiếng Việt. Chỉ trả về JSON hợp lệ theo schema.\n"
        "Các intent hợp lệ: 'assemble_pc' (tư vấn lắp ráp máy), 'shopping' (mua/đặt hàng), 'warranty' (bảo hành), hoặc 'unknown'.\n"
        "Nếu 'unknown', hãy tạo 1–2 câu hỏi làm rõ bằng tiếng Việt, lịch sự, ngắn gọn.\n"
        "Ưu tiên câu hỏi hiện tại hơn các câu trước. Hỗ trợ từ khóa song ngữ Việt–Anh.\n"
        "Schema JSON:\n"
        "{\"intent\":\"assemble_pc|shopping|warranty|unknown\",\"confidence\":0.0,\"need_retrieval\":false,\"clarify_needed\":false,\"clarify_questions\":[\"\"],\"rationale\":\"\"}\n"
        f"latest_user_message: {latest!r}\n"
        f"recent_user_messages: {recents!r}\n"
        "Chỉ in JSON, KHÔNG kèm giải thích khác."
    )

    intent = "unknown"
    confidence = 0.0
    need_retrieval = False
    clarify_needed = False
    clarify_questions: List[str] = []

    try:
        # Use sync generate_text; consistent with respond_node's pattern
        raw = generate_text(prompt, model="gpt-oss")
        logger.info(f"Classify raw: {raw}")
        data = None
        try:
            data = loads(raw)
        except Exception:
            # Sometimes the model may wrap or produce extra text; try to find JSON object
            import re
            m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if m:
                data = loads(m.group(0))
        if isinstance(data, dict):
            intent = str(data.get("intent", "unknown"))
            confidence = float(data.get("confidence", 0.0))
            need_retrieval = bool(data.get("need_retrieval", False))
            clarify_needed = bool(data.get("clarify_needed", False))
            cq = data.get("clarify_questions") or []
            if isinstance(cq, list):
                clarify_questions = [str(x) for x in cq if x]
    except Exception:
        logger.exception("Classify node: LLM classification failed, using heuristic fallback")

    # Fallbacks
    if intent not in {"assemble_pc", "shopping", "warranty", "unknown"}:
        intent = "unknown"

    if latest and (intent == "unknown" or confidence < INTENT_CONFIDENCE_THRESHOLD):
        h = _keyword_heuristic_intent(latest)
        if h != "unknown":
            intent = h
            confidence = max(confidence, max(0.6, INTENT_CONFIDENCE_THRESHOLD))

    # Derive need_retrieval if not provided
    if need_retrieval is False and intent in {"assemble_pc", "shopping", "warranty"}:
        need_retrieval = _need_retrieval_for_intent(intent, latest or "")

    # Clarify if still unknown or low confidence
    if intent == "unknown" or confidence < INTENT_CONFIDENCE_THRESHOLD:
        clarify_needed = True
        # Normalize to a fixed clarify question (language-aware) for reliable attempt counting
        DEFAULT_CLARIFY_Q_VI = "Để mình hỗ trợ chính xác, bạn đang cần tư vấn lắp ráp máy, hỏi thông tin mua hàng hay bảo hành ạ?"
        DEFAULT_CLARIFY_Q_EN = "To help you accurately, are you looking for PC build advice, shopping/product info, or warranty support?"
        DEFAULT_CLARIFY_Q = DEFAULT_CLARIFY_Q_EN if preferred_lang == "en" else DEFAULT_CLARIFY_Q_VI
        clarify_questions = [DEFAULT_CLARIFY_Q]

    # Count clarify attempts from chat_history
    attempts = 0
    try:
        DEFAULT_CLARIFY_Q = (
            "To help you accurately, are you looking for PC build advice, shopping/product info, or warranty support?"
            if preferred_lang == "en"
            else "Để mình hỗ trợ chính xác, bạn đang cần tư vấn lắp ráp máy, hỏi thông tin mua hàng hay bảo hành ạ?"
        )
        for msg in state.get("chat_history", []):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                if isinstance(content, str) and content.strip() == DEFAULT_CLARIFY_Q:
                    attempts += 1
    except Exception:
        attempts = 0

    # No farewell cutoff: we keep clarifying gently until the intent is clear

    # Update state
    state["intent"] = intent
    state["intent_confidence"] = confidence
    state["need_retrieval_hint"] = need_retrieval
    state["clarify_questions"] = clarify_questions
    state["clarify_attempts"] = attempts

    # Log compact line
    try:
        logger.info(
            f"intent={intent} conf={confidence:.2f} retrieve={need_retrieval} clarify={clarify_needed} cid={state.get('conversation_id')} uid={state.get('user_id')}"
        )
    except Exception:
        pass

    return {
        "need_retrieval": need_retrieval,
        "intent": intent,
        "clarify_needed": clarify_needed,
        "clarify_questions": clarify_questions,
        "clarify_attempts": attempts,
    }


def build_prompt(state: AgentState) -> str:
    """Build a simple prompt from chat history and retrieved context."""
    parts = []
    # Include persona if configured
    try:
        persona_path = os.environ.get("PERSONA_PATH", str(pathlib.Path.cwd() / "prompts/system_persona_vi.md"))
        pp = pathlib.Path(persona_path)
        if pp.exists():
            parts.append("System Persona:")
            parts.append(pp.read_text(encoding="utf-8")[:PERSONA_MAX_CHARS])  # cap by env
    except Exception:
        pass
    # include retrieved context first if present
    rc = state.get("retrieved_context") or []
    if rc:
        parts.append("Retrieved context:")
        for d in rc:
            parts.append(d.get("text") or d.get("content") or str(d))

    # Instruction: concise Vietnamese answer and include detected intent if any
    intent = state.get("intent")
    if intent and intent != "unknown":
        parts.append(f"Detected intent: {intent}")
    lang = state.get("preferred_language") or "vi"
    if lang == "en":
        parts.append("Instruction: Answer in English, concise (~5 sentences), clear, and to the point.")
    else:
        parts.append("Instruction: Trả lời bằng tiếng Việt, ngắn gọn (~5 câu), rõ ràng, tránh lan man.")

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
        "response": None,
        "stream": False,
        "intent": "unknown",
        "intent_confidence": 0.0,
        "need_retrieval_hint": False,
        "clarify_questions": [],
        "clarify_attempts": 0,
    "preferred_language": "vi",
    }
    
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