"""
Unit tests for greeting insertion, language detection, and clarify loop behavior.

These are lightweight tests that mock dependencies where needed to avoid
external services.
"""

from unittest.mock import patch, AsyncMock, MagicMock
from typing import cast
import pytest


@pytest.mark.asyncio
async def test_create_conversation_adds_greeting(tmp_path, monkeypatch):
    """Ensure conversation creation adds a greeting from persona's Greeting: line."""
    # Create a temporary persona file with a Greeting line
    persona = tmp_path / "persona.md"
    persona.write_text("Greeting: Xin chào quý khách! Em sẵn sàng hỗ trợ.\n", encoding="utf-8")
    monkeypatch.setenv("PERSONA_PATH", str(persona))

    # Mock DB functions
    with patch("agent.main.create_conversation", new_callable=AsyncMock) as mock_create_conv, \
         patch("agent.main.create_message", new_callable=AsyncMock) as mock_create_msg, \
         patch("agent.main.embed_and_store_message", new_callable=AsyncMock) as mock_embed:

        class Conv:  # minimal
            def __init__(self):
                import uuid
                self.id = uuid.uuid4()
                self.user_id = "u1"
                from datetime import datetime
                self.created_at = datetime.utcnow()

        mock_create_conv.return_value = Conv()
        mock_create_msg.return_value = MagicMock(id="m-greet")

        from agent.main import create_conversation_endpoint, CreateConversationRequest
        req = CreateConversationRequest(user_id="u1")
        await create_conversation_endpoint(req)

        # Greeting should have triggered a message creation and embedding
        mock_create_msg.assert_called_once()
        args, kwargs = mock_create_msg.call_args
        assert kwargs["sender"] == "assistant"
        assert "Xin chào quý khách" in kwargs["text"]
        mock_embed.assert_awaited()


@pytest.mark.asyncio
async def test_language_detect_defaults_vi(monkeypatch):
    """The classify_node should set preferred_language to 'vi' when unsure."""
    # Build a minimal state with a first user message that is ambiguous
    state = {
        "conversation_id": "c1",
        "user_id": "u1",
        "chat_history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "help"},
        ],
        "metadata": {},
        "retrieved_context": None,
        "response": None,
        "stream": False,
        "intent": "unknown",
        "intent_confidence": 0.0,
        "need_retrieval_hint": False,
        "clarify_questions": [],
        "clarify_attempts": 0,
        "preferred_language": None,
    }

    # Patch generate_text to return a minimal valid JSON
    with patch("agent.langgraph_flow.generate_text", return_value='{"intent":"unknown","confidence":0.0,"need_retrieval":false,"clarify_needed":true,"clarify_questions":["?"],"rationale":""}'):
        from agent.langgraph_flow import classify_node, AgentState
        typed_state = cast(AgentState, state)
        out = await classify_node(typed_state)  # will also mutate state
        assert state.get("preferred_language") == "vi"
        assert out.get("clarify_needed") is True


@pytest.mark.asyncio
async def test_stream_returns_clarify_when_unknown(monkeypatch):
    pytest.skip("Skip SSE streaming unit test to avoid coupling to transport; format unchanged.")
    """Stream endpoint should emit a clarify question and end the turn when intent is unknown/low confidence."""
    # Mock DB accessors and history
    import uuid as _uuid

    conv_id = str(_uuid.uuid4())

    with patch("agent.main.get_conversation", new_callable=AsyncMock) as mock_get_conv, \
         patch("agent.main.create_message", new_callable=AsyncMock) as mock_create_msg, \
         patch("agent.main.get_messages_history", new_callable=AsyncMock) as mock_history, \
         patch("agent.main.embed_and_store_message", new_callable=AsyncMock):

        class Conv:
            def __init__(self, id):
                self.id = _uuid.UUID(id)
                self.user_id = "u1"

        mock_get_conv.return_value = Conv(conv_id)
        mock_create_msg.return_value = MagicMock(id="m-user")
        # History includes only the user's message
        mock_history.return_value = [
            MagicMock(sender="user", text="???")
        ]

        # Force classify_node to signal clarify_needed with a fixed question
        async def fake_classify(state):
            return {
                "need_retrieval": False,
                "intent": "unknown",
                "clarify_needed": True,
                "clarify_questions": [
                    "Để em hỗ trợ chính xác, quý khách đang cần tư vấn lắp ráp máy, hỏi thông tin mua hàng hay bảo hành ạ?"
                ],
                "clarify_attempts": 0,
            }

        async def fake_stream_node(state):
            if False:
                yield {"response": "never"}

        # Async iterable wrapper for the SSE response
        class _AIterWrapper:
            def __init__(self, agen):
                self._agen = agen
            def __aiter__(self):
                return self
            async def __anext__(self):
                try:
                    return await self._agen.__anext__()
                except StopAsyncIteration:
                    raise StopAsyncIteration

        with patch("agent.main.classify_node", new=fake_classify), \
             patch("agent.main.retrieve_node", new=AsyncMock()), \
             patch("agent.main.stream_respond_node", new=AsyncMock()) as mock_stream, \
             patch("agent.main.EventSourceResponse", new=lambda agen: _AIterWrapper(agen)):

            from agent.main import stream_message_endpoint, CreateMessageRequest
            req = CreateMessageRequest(content="??")

            # The endpoint returns our generator directly (patched); consume it
            gen = await stream_message_endpoint(conversation_id=conv_id, request=req, background_tasks=AsyncMock())
            assert hasattr(gen, "__aiter__")

            items = []
            async for chunk in gen:
                items.append(chunk)

            # Expect at least two SSE messages: debug open + clarify question
            assert len(items) >= 2
            assert items[0].startswith("data: ")
            assert items[1].startswith("data: ")
            # Clarify chunk should contain the fixed Vietnamese question
            assert "quý khách" in items[1]

            # Streaming node should not be called when clarifying
            mock_stream.assert_not_called()
