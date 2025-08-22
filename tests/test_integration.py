"""
Smoke integration tests for the Mai-Sale chat application.

These tests verify the end-to-end flow of the application:
- Creating a conversation
- Sending a message
- Checking that the response is saved
- (Optional) Verifying retrieval works if KB matches
"""

import pytest
import requests
import time
import os

# Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "default-dev-key"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def backend():
    """Fixture to start and stop the backend for integration tests."""
    # Note: In a real scenario, you would start the backend here
    # For this example, we assume the backend is already running
    # You could use pytest-docker or similar to manage this
    yield
    # Cleanup code would go here if needed

def test_create_conversation(backend):
    """Test creating a conversation."""
    response = requests.post(
        f"{API_BASE_URL}/conversations",
        headers=HEADERS,
        json={"user_id": "integration-test-user"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["user_id"] == "integration-test-user"
    return data["id"]

def test_send_message_and_get_history(backend):
    """Test sending a message and retrieving history."""
    # First create a conversation
    conv_response = requests.post(
        f"{API_BASE_URL}/conversations",
        headers=HEADERS,
        json={"user_id": "integration-test-user-2"}
    )
    assert conv_response.status_code == 201
    conversation_id = conv_response.json()["id"]
    
    # Send a message
    message_content = "Hello, this is an integration test message."
    msg_response = requests.post(
        f"{API_BASE_URL}/conversations/{conversation_id}/messages",
        headers=HEADERS,
        json={"content": message_content}
    )
    
    assert msg_response.status_code == 202
    msg_data = msg_response.json()
    assert "message_id" in msg_data
    
    # Wait a bit to ensure processing (if there were background tasks)
    time.sleep(1)
    
    # Get history
    history_response = requests.get(
        f"{API_BASE_URL}/conversations/{conversation_id}/history",
        headers=HEADERS
    )
    
    assert history_response.status_code == 200
    history_data = history_response.json()
    assert "messages" in history_data
    messages = history_data["messages"]
    
    # Should have at least the user message
    assert len(messages) >= 1
    
    # Find the user message in the history
    user_message = None
    for msg in messages:
        if msg["sender"] == "user" and msg["content"] == message_content:
            user_message = msg
            break
            
    assert user_message is not None, "User message not found in history"

# Note: A more comprehensive integration test would also:
# - Test that the assistant response is generated and saved
# - Test retrieval functionality if KB is set up
# - Test error cases