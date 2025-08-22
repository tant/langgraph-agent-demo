# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "gradio",
#     "requests",
# ]
# ///
"""
Minimal Gradio UI for the Mai-Sale chat application.

This script creates a simple chat interface using Gradio that communicates
with the FastAPI backend via REST API calls.
"""

import gradio as gr
import requests
import json
import os
import uuid
from typing import List, Tuple, Dict, Any

# --- Configuration ---
DEFAULT_API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
DEFAULT_API_KEY = os.environ.get("X_API_KEY", "default-dev-key")

# --- Global State (for simplicity in this minimal UI) ---
# In a real application, you would use Gradio's state or session management
current_conversation_id: str = ""
api_base: str = DEFAULT_API_BASE
api_key: str = DEFAULT_API_KEY

# --- API Client Functions ---
def create_conversation(api_base: str, api_key: str, user_id: str = "gradio-user") -> str:
    """Create a new conversation via the API."""
    url = f"{api_base}/conversations"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    data = {"user_id": user_id}
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["id"]

def send_message(api_base: str, api_key: str, conversation_id: str, content: str) -> str:
    """Send a user message via the API."""
    url = f"{api_base}/conversations/{conversation_id}/messages"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    data = {"content": content}
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["message_id"]

def get_history(api_base: str, api_key: str, conversation_id: str) -> List[Dict[str, Any]]:
    """Get conversation history via the API."""
    url = f"{api_base}/conversations/{conversation_id}/history"
    headers = {"X-API-Key": api_key}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["messages"]

# --- UI Logic Functions ---
def start_new_conversation(api_base_input: str, api_key_input: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Start a new conversation."""
    global current_conversation_id, api_base, api_key
    api_base = api_base_input
    api_key = api_key_input
    
    try:
        current_conversation_id = create_conversation(api_base, api_key)
        return f"New conversation started with ID: {current_conversation_id}", []
    except Exception as e:
        return f"Error creating conversation: {e}", []

def respond(user_message: str, chat_history: List[Tuple[str, str]], api_base_input: str, api_key_input: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Handle user message and generate response."""
    global current_conversation_id, api_base, api_key
    api_base = api_base_input
    api_key = api_key_input
    
    if not current_conversation_id:
        return "Please start a new conversation first.", chat_history
        
    try:
        # Send user message
        send_message(api_base, api_key, current_conversation_id, user_message)
        
        # Get updated history
        messages = get_history(api_base, api_key, current_conversation_id)
        
        # Format chat history for Gradio
        formatted_history = []
        for msg in messages:
            sender = msg["sender"]
            content = msg["content"]
            if sender in ["user", "assistant"]:
                formatted_history.append((content, None if sender == "user" else content))
                
        return "", formatted_history
    except Exception as e:
        return f"Error sending message or getting history: {e}", chat_history

# --- Gradio Interface ---
with gr.Blocks(title="Mai-Sale Chat") as demo:
    gr.Markdown("# Mai-Sale Chat")
    gr.Markdown("A minimal chat interface for the Mai-Sale RAG chat application.")
    
    # API Configuration
    with gr.Row():
        api_base_input = gr.Textbox(label="API Base URL", value=DEFAULT_API_BASE)
        api_key_input = gr.Textbox(label="API Key", value=DEFAULT_API_KEY, type="password")
        new_conv_btn = gr.Button("New Conversation")
        
    # Status display
    status_display = gr.Textbox(label="Status", interactive=False)
    
    # Chatbot
    chatbot = gr.Chatbot(label="Chat History")
    user_input = gr.Textbox(label="Your Message", placeholder="Type your message here...")
    send_btn = gr.Button("Send")
    
    # Event handling
    new_conv_btn.click(
        fn=start_new_conversation,
        inputs=[api_base_input, api_key_input],
        outputs=[status_display, chatbot]
    )
    
    send_btn.click(
        fn=respond,
        inputs=[user_input, chatbot, api_base_input, api_key_input],
        outputs=[user_input, chatbot]
    )
    
    user_input.submit(
        fn=respond,
        inputs=[user_input, chatbot, api_base_input, api_key_input],
        outputs=[user_input, chatbot]
    )

# --- Main Execution ---
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)