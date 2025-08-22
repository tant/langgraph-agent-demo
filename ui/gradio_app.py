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
import time
from typing import List, Tuple, Dict, Any, Generator

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

def stream_message(api_base: str, api_key: str, conversation_id: str, content: str) -> Generator[str, None, None]:
    """Send a user message and stream the response via the API using SSE."""
    url = f"{api_base}/conversations/{conversation_id}/stream"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json", "Accept": "text/event-stream"}
    data = {"content": content}
    
    print(f"UI_DEBUG: Connecting to {url} for streaming (SSE)...")
    try:
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            print(f"UI_DEBUG: Response status code: {response.status_code}")
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    print(f"UI_DEBUG: Received line: '{decoded_line}'")
                    if decoded_line.startswith('data:'):
                        try:
                            # Extract the JSON string after "data: "
                            json_data = json.loads(decoded_line[5:])
                            chunk = json_data.get("chunk", "")
                            if chunk:
                                print(f"UI_DEBUG: Parsed chunk: '{chunk}'")
                                yield chunk
                        except json.JSONDecodeError:
                            print(f"UI_WARN: Could not decode JSON from line: {decoded_line}")
                            continue
    except requests.exceptions.RequestException as e:
        print(f"UI_ERROR: Request failed: {e}")
        raise
    print("UI_DEBUG: Stream finished.")


def start_new_conversation(api_base_input: str, api_key_input: str) -> Tuple[str, List, str]:
    """Start a new conversation and clear the chat."""
    global current_conversation_id, api_base, api_key
    api_base = api_base_input
    api_key = api_key_input
    
    try:
        user_id = f"gradio-user-{uuid.uuid4()}"
        current_conversation_id = create_conversation(api_base, api_key, user_id)
        print(f"UI_DEBUG: Started new conversation: {current_conversation_id}")
        return f"New conversation started: {current_conversation_id}", [], ""
    except Exception as e:
        print(f"UI_ERROR: Could not start new conversation: {e}")
        return f"Error: {e}", [], ""


def add_user_message_and_stream_bot_response(
    user_message: str, 
    chat_history: List[Dict[str, str]], 
    api_base_input: str, 
    api_key_input: str
) -> Generator[Tuple[str, List[Dict[str, str]]], None, None]:
    """
    Adds the user message to the chat, then streams the bot's response.
    This single function handles the entire interaction flow after the user hits enter.
    Uses the 'messages' format for Gradio Chatbot.
    """
    global current_conversation_id, api_base, api_key
    api_base = api_base_input
    api_key = api_key_input

    if not user_message:
        yield "", chat_history
        return

    print(f"UI_DEBUG: User message received: '{user_message}'")
    # Add user message to history
    chat_history.append({"role": "user", "content": user_message})
    # Add a placeholder for the bot's response
    chat_history.append({"role": "assistant", "content": ""})
    print(f"UI_DEBUG: Yielding initial history: {chat_history}")
    yield "", chat_history

    if not current_conversation_id:
        try:
            user_id = f"gradio-user-{uuid.uuid4()}"
            current_conversation_id = create_conversation(api_base, api_key, user_id)
            print(f"UI_DEBUG: Created new conversation: {current_conversation_id}")
        except Exception as e:
            error_message = f"Error starting conversation: {e}"
            chat_history[-1]["content"] = error_message
            print(f"UI_ERROR: {error_message}")
            yield "", chat_history
            return

    try:
        # Stream the bot's response
        response_stream = stream_message(api_base, api_key, current_conversation_id, user_message)
        for i, chunk in enumerate(response_stream):
            chat_history[-1]["content"] += chunk
            print(f"UI_DEBUG: Yielding history with chunk {i}")
            yield "", chat_history
    except requests.exceptions.RequestException as e:
        error_message = f"API Error: {e}"
        chat_history[-1]["content"] = error_message
        print(f"UI_ERROR: {error_message}")
        yield "", chat_history
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        chat_history[-1]["content"] = error_message
        print(f"UI_ERROR: {error_message}")
        yield "", chat_history
    
    print("UI_DEBUG: Bot response function finished.")


# --- Gradio UI Layout ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Mai-Sale — Gradio Demo")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Connection")
            api_base_input = gr.Textbox(label="API Base URL", value=DEFAULT_API_BASE)
            api_key_input = gr.Textbox(label="API Key", value=DEFAULT_API_KEY, type="password")
            start_button = gr.Button("Start New Conversation")
            conversation_status = gr.Textbox(label="Status", interactive=False)

        with gr.Column(scale=4):
            chatbot = gr.Chatbot(
                [],
                elem_id="chatbot",
                bubble_full_width=False,
                height=600,
                label="Chat",
                type="messages"  # Use the recommended 'messages' type
            )

            with gr.Row():
                msg = gr.Textbox(
                    scale=4,
                    show_label=False,
                    placeholder="Enter text and press enter",
                    container=False,
                )
                # Not using the upload button for now
                # upload_button = gr.UploadButton("📁", file_types=["image", "video", "audio"])

    # --- Event Handlers ---
    start_button.click(
        start_new_conversation,
        inputs=[api_base_input, api_key_input],
        outputs=[conversation_status, chatbot, msg]
    )

    msg.submit(
        add_user_message_and_stream_bot_response,
        inputs=[msg, chatbot, api_base_input, api_key_input],
        outputs=[msg, chatbot]
    )

if __name__ == "__main__":
    demo.launch(debug=True)