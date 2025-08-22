"""
Unit tests for the database module.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from agent.database import create_conversation, get_conversation, create_message, get_messages_history
import uuid

# We'll need to mock the SQLAlchemy async session and engine for unit tests
# This is a simplified example, in practice you might use a test database or more sophisticated mocks

@pytest.fixture
def mock_session():
    """Fixture to provide a mocked async session."""
    with patch('agent.database.async_session') as mock_sessionmaker:
        mock_session = MagicMock()
        mock_sessionmaker.return_value.__aenter__.return_value = mock_session
        yield mock_session

def test_create_conversation(mock_session):
    """Test creating a conversation."""
    # Mock the conversation object that would be returned
    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.user_id = "test-user"
    mock_conversation.metadata_ = None
    
    # Configure the mock session
    mock_session.get.return_value = mock_conversation
    # Mock the refresh to set attributes on the mock
    mock_session.refresh.side_effect = lambda obj: setattr(obj, 'id', mock_conversation.id) or setattr(obj, 'user_id', mock_conversation.user_id)
    
    # Run the async function in a new event loop to avoid issues with pytest's default loop
    async def run_test():
        result = await create_conversation("test-user")
        assert result.user_id == "test-user"
        assert isinstance(result.id, uuid.UUID)
        
    asyncio.run(run_test())

def test_get_conversation(mock_session):
    """Test getting a conversation."""
    # Mock the conversation object that would be returned
    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.user_id = "test-user"
    
    mock_session.get.return_value = mock_conversation
    
    # Run the async function
    async def run_test():
        result = await get_conversation(mock_conversation.id)
        assert result == mock_conversation
        
    asyncio.run(run_test())

def test_get_conversation_not_found(mock_session):
    """Test getting a conversation that doesn't exist."""
    mock_session.get.return_value = None
    
    # Run the async function
    async def run_test():
        result = await get_conversation(uuid.uuid4())
        assert result is None
        
    asyncio.run(run_test())

# Note: Testing create_message and get_messages_history would follow similar patterns
# For brevity, we'll skip those in this example, but they would be included in a full test suite