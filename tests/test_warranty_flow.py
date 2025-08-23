from datetime import date

import pytest


@pytest.mark.asyncio
async def test_warranty_node_db_lookup_found(monkeypatch):
    # Arrange state with prior assistant asking for serial and a user providing one
    from agent.langgraph_flow import warranty_stream_node, AgentState

    state: AgentState = {
        "conversation_id": "c1",
        "user_id": "u1",
        "chat_history": [
            {"role": "assistant", "content": "Quý khách vui lòng cung cấp số serial của sản phẩm để em kiểm tra thời hạn bảo hành ạ?"},
            {"role": "user", "content": "SN ABC123-999"},
        ],
        "metadata": {},
        "preferred_language": "vi",
        "retrieved_context": None,
        "response": None,
        "stream": True,
        "intent": "warranty",
        "intent_confidence": 0.9,
        "need_retrieval_hint": False,
        "clarify_questions": [],
        "clarify_attempts": 0,
    }

    class DummyRec:
        product_name = "Test Product"
        warranty_end_date = date(2026, 8, 12)

    # Force DB mode
    monkeypatch.setenv("PERSONA_PATH", "")  # avoid reading filesystem

    # Patch database helper used inside the node
    import agent.database as db

    async def fake_get_warranty_by_serial(s):
        return DummyRec()

    monkeypatch.setattr(db, "get_warranty_by_serial", fake_get_warranty_by_serial, raising=True)

    # Act
    chunks = []
    async for out in warranty_stream_node(state):
        chunks.append(out["response"])  # type: ignore[index]

    # Assert
    assert any("Thông tin bảo hành" in c for c in chunks)


@pytest.mark.asyncio
async def test_warranty_node_db_lookup_not_found(monkeypatch):
    from agent.langgraph_flow import warranty_stream_node, AgentState

    state: AgentState = {
        "conversation_id": "c1",
        "user_id": "u1",
        "chat_history": [
            {"role": "assistant", "content": "Quý khách vui lòng cung cấp số serial của sản phẩm để em kiểm tra thời hạn bảo hành ạ?"},
            {"role": "user", "content": "XYZ-000"},
        ],
        "metadata": {},
        "preferred_language": "vi",
        "retrieved_context": None,
        "response": None,
        "stream": True,
        "intent": "warranty",
        "intent_confidence": 0.9,
        "need_retrieval_hint": False,
        "clarify_questions": [],
        "clarify_attempts": 0,
    }

    import agent.database as db

    async def fake_get_warranty_by_serial(s):
        return None

    monkeypatch.setattr(db, "get_warranty_by_serial", fake_get_warranty_by_serial, raising=True)

    chunks = []
    async for out in warranty_stream_node(state):
        chunks.append(out["response"])  # type: ignore[index]

    assert any("chưa có trên hệ thống" in c for c in chunks)
