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

import re
import logging
from typing import List, Tuple, Dict, Any, Generator


_ui_logger = logging.getLogger("gradio_ui")

def ui_log(msg: str):
    """Log UI debug messages via the standard logging system at DEBUG level.
    This makes it possible to enable/disable with normal logging configuration.
    """
    _ui_logger.debug(msg)


def _smart_append(existing: str, chunk: str) -> str:
    """Append chunk to existing text with simple spacing/newline heuristics.
    - If chunk is empty, return existing.
    - If chunk is purely newlines, collapse to two newlines.
    - If chunk starts with whitespace, append directly.
    - If chunk starts with punctuation (.,:;!?), append directly without extra space.
    - Otherwise, insert a space if existing doesn't already end with whitespace or is empty.
    """
    if not chunk:
        return existing

    # Normalize long runs of newlines to at most two
    if all(c == "\n" for c in chunk):
        nl = "\n\n"
        if existing.endswith(nl):
            return existing
        return existing + nl

    # If chunk starts with whitespace (including leading space), append as-is
    if chunk[0].isspace():
        return existing + chunk

    # If chunk starts with punctuation that should not have a space before it
    if chunk[0] in ",.:;!?)]}" or (chunk[0] in "'\"" and existing.endswith(" ")):
        return existing + chunk

    # Otherwise decide whether to insert a space or concatenate directly.
    if existing and not existing[-1].isspace():
        last_char = existing[-1]
        first_char = chunk[0]
        # If the last char and first char are both alphanumeric (letters or digits),
        # they are likely parts of the same word/subword and should be concatenated
        # without an extra space. This helps with tokenized fragments like "Thi" + "ết" -> "Thiết".
        if last_char.isalnum() and first_char.isalnum():
            return existing + chunk
        # If chunk starts with punctuation that attaches to the previous word, append directly
        if first_char in ",.:;!?)]}" or (first_char in "'\"" and existing.endswith(" ")):
            return existing + chunk
        # Otherwise insert a space to separate words
        return existing + " " + chunk
    else:
        return existing + chunk

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
    
    ui_log(f"POST {url} payload={data}")
    response = requests.post(url, headers=headers, json=data)
    ui_log(f"Response status: {response.status_code}")
    try:
        ui_log(f"Response body: {response.text}")
        response.raise_for_status()
        return response.json()["id"]
    except Exception as e:
        ui_log(f"Error creating conversation: {e}")
        raise

def send_message(api_base: str, api_key: str, conversation_id: str, content: str) -> str:
    """Send a user message via the API."""
    url = f"{api_base}/conversations/{conversation_id}/messages"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    data = {"content": content}
    
    ui_log(f"POST {url} payload={data}")
    response = requests.post(url, headers=headers, json=data)
    ui_log(f"Response status: {response.status_code}")
    ui_log(f"Response headers: {dict(response.headers)}")
    try:
        ui_log(f"Response body: {response.text}")
        response.raise_for_status()
        return response.json().get("message_id") or response.json().get("id")
    except Exception as e:
        ui_log(f"Error sending message: {e}")
        raise

def get_history(api_base: str, api_key: str, conversation_id: str) -> List[Dict[str, Any]]:
    """Get conversation history via the API."""
    url = f"{api_base}/conversations/{conversation_id}/history"
    headers = {"X-API-Key": api_key}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["messages"]

def stream_message(api_base: str, api_key: str, conversation_id: str, content: str) -> Generator[str, None, None]:
    """Send a user message and stream the response via the API using SSE.
    Robust parser: buffer incoming bytes, split on '\n\n' event boundary, handle multiple 'data:' lines per event.
    """
    url = f"{api_base}/conversations/{conversation_id}/stream"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json", "Accept": "text/event-stream"}
    data = {"content": content}

    ui_log(f"Connecting to {url} for streaming (SSE) ...")
    try:
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            ui_log(f"Response status code: {response.status_code}")
            ui_log(f"Response headers: {dict(response.headers)}")
            try:
                response.raise_for_status()
            except Exception as e:
                ui_log(f"Stream connect failed: {e}; body={response.text}")
                raise

            buffer = ""
            # Use iter_content to get raw chunks; iter_lines can combine events unpredictably
            for chunk_bytes in response.iter_content(chunk_size=1024):
                if not chunk_bytes:
                    continue
                try:
                    decoded = chunk_bytes.decode("utf-8")
                except Exception:
                    decoded = chunk_bytes.decode("utf-8", errors="replace")
                # Normalize CRLF to LF so we reliably detect SSE boundaries ("\n\n")
                decoded = decoded.replace('\r\n', '\n').replace('\r', '\n')
                buffer += decoded
                ui_log(f"Appended decoded chunk to buffer (len now {len(buffer)})")

                # Process events in buffer. Prefer proper '\n\n' separated SSE events, but
                # also extract complete '"chunk": "..."' occurrences when the server
                # sends concatenated 'data:' payloads without event separators.
                while True:
                    # 1) Normal SSE event boundary
                    if "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        event = event.strip()
                        if not event:
                            continue
                        ui_log(f"Processing complete SSE event: {event!r}")

                        # Collect all data: lines in the event
                        data_lines = []
                        for line in event.splitlines():
                            line = line.strip()
                            if line.startswith("data:"):
                                data_lines.append(line[5:].strip())
                            else:
                                ui_log(f"Ignoring non-data line in event: {line!r}")

                        if not data_lines:
                            ui_log("No data: lines found in event; skipping")
                            continue

                        payload = "\n".join(data_lines)
                        # If payload starts with a simple debug JSON object followed by text
                        # (e.g. '{"debug":"stream-open"} rest...'), strip that leading
                        # JSON so we only present the assistant text to the UI.
                        m_debug = re.match(r'^\s*(\{[^}]*\})\s*(.*)$', payload, flags=re.S)
                        if m_debug:
                            try:
                                maybe_obj = json.loads(m_debug.group(1))
                                if isinstance(maybe_obj, dict) and "debug" in maybe_obj:
                                    ui_log(f"Stripped leading debug object: {maybe_obj}")
                                    payload = m_debug.group(2)
                                    if not payload:
                                        # Nothing left after the debug object
                                        continue
                            except Exception:
                                # If parsing fails, fall back to normal handling
                                pass
                        # Ignore debug/handshake events
                        try:
                            maybe_json = json.loads(payload)
                            if isinstance(maybe_json, dict) and "debug" in maybe_json:
                                ui_log(f"Ignoring debug SSE event: {maybe_json}")
                                continue
                            chunk = maybe_json.get("chunk") if isinstance(maybe_json, dict) else None
                            if chunk is not None:
                                ui_log(f"Parsed chunk (json): '{chunk}'")
                                yield str(chunk)
                                continue
                        except Exception:
                            # Not valid JSON or didn't contain chunk; try regex extraction
                            pass

                        matches = re.findall(r'"chunk"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', payload)
                        if matches:
                            for raw in matches:
                                try:
                                    parsed = json.loads(f'"{raw}"')
                                except Exception:
                                    parsed = raw
                                ui_log(f"Parsed chunk (multi-regex): '{parsed}'")
                                yield str(parsed)
                            continue

                        cleaned = payload
                        if cleaned.startswith("data:"):
                            cleaned = cleaned[len("data:"):].strip()
                        ui_log(f"Using raw payload as chunk (final fallback): '{cleaned}'")
                        yield cleaned
                        continue

                    # 2) If no '\n\n' boundary, try to find standalone '"chunk": "..."' anywhere
                    m = re.search(r'"chunk"\s*:\s*"(?:(?:\\.)|[^"\\])*"', buffer)
                    if m:
                        # Extract inner string value robustly
                        inner_m = re.search(r'"chunk"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', m.group(0))
                        if inner_m:
                            raw = inner_m.group('val')
                            try:
                                parsed = json.loads(f'"{raw}"')
                            except Exception:
                                parsed = raw
                            ui_log(f"Parsed chunk (inline match): '{parsed}'")
                            yield str(parsed)
                            # Remove the matched span from the buffer to avoid re-processing
                            start, end = m.span()
                            buffer = buffer[:start] + buffer[end:]
                            continue

                    # Nothing more to process right now
                    break

            # After stream ends, if buffer has leftover data, try to process it
                    if buffer.strip():
                        ui_log(f"Stream closed with leftover buffer: {buffer!r}")
                        # Try to robustly handle concatenated 'data:' segments that may lack event separators
                        event = buffer.strip()

                        # If leftover begins with a leading debug JSON object, strip it first.
                        m_debug_left = re.match(r'^\s*(\{[^}]*\})\s*(.*)$', event, flags=re.S)
                        if m_debug_left:
                            try:
                                maybe_obj = json.loads(m_debug_left.group(1))
                                if isinstance(maybe_obj, dict) and "debug" in maybe_obj:
                                    ui_log(f"Stripped leading debug object in leftover: {maybe_obj}")
                                    event = m_debug_left.group(2) or ""
                            except Exception:
                                pass

                        # First, try to directly extract all "chunk" values via regex across the entire leftover
                        matches = re.findall(r'"chunk"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', event)
                        if matches:
                            for raw in matches:
                                try:
                                    parsed = json.loads(f'"{raw}"')
                                except Exception:
                                    parsed = raw
                                ui_log(f"Parsed final chunk (multi-regex): '{parsed}'")
                                yield str(parsed)
                            return

                        # Next, try to find explicit 'data: { ... }' JSON objects even when concatenated
                        json_objs = []
                        for m in re.finditer(r'data:\s*(\{(?:[^{}]|(?R))*\})', event, flags=re.S):
                            # Fallback safe capture without heavy recursion: match balanced braces roughly
                            try:
                                obj_text = m.group(1)
                                json_objs.append(obj_text)
                            except Exception:
                                continue

                        if json_objs:
                            for obj_text in json_objs:
                                try:
                                    json_data = json.loads(obj_text)
                                    chunk = json_data.get("chunk") if isinstance(json_data, dict) else None
                                    if chunk is not None:
                                        ui_log(f"Parsed final chunk from concatenated data: '{chunk}'")
                                        yield str(chunk)
                                        continue
                                except Exception:
                                    pass
                                # If we couldn't parse JSON, yield the raw object text as fallback
                                ui_log(f"Yielding raw final object text: '{obj_text[:60]}'")
                                yield obj_text
                            return

                        # Last resort: yield the raw leftover buffer
                        ui_log(f"Using leftover buffer as raw final chunk (last resort): '{event[:200]}'")
                        yield event

    except requests.exceptions.RequestException as e:
        ui_log(f"Request failed: {e}")
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
        ui_log(f"Started new conversation: {current_conversation_id}")
        # Fetch history immediately so the greeting (assistant) shows up in UI
        try:
            msgs = get_history(api_base, api_key, current_conversation_id)
            # Map API messages to Chatbot(messages) format
            chat_history = [
                {"role": m.get("sender", "assistant"), "content": m.get("content", "")}
                for m in msgs
            ]
        except Exception as he:
            ui_log(f"Failed to fetch history for new conversation: {he}")
            chat_history = []
        return f"New conversation started: {current_conversation_id}", chat_history, ""
    except Exception as e:
        ui_log(f"Could not start new conversation: {e}")
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

    ui_log(f"User message received: '{user_message}'")
    # Add user message to history
    chat_history.append({"role": "user", "content": user_message})
    # Add a placeholder for the bot's response
    chat_history.append({"role": "assistant", "content": ""})
    ui_log(f"Yielding initial history: {chat_history}")
    yield "", chat_history

    if not current_conversation_id:
        try:
            user_id = f"gradio-user-{uuid.uuid4()}"
            current_conversation_id = create_conversation(api_base, api_key, user_id)
            ui_log(f"Created new conversation: {current_conversation_id}")
        except Exception as e:
            error_message = f"Error starting conversation: {e}"
            chat_history[-1]["content"] = error_message
            ui_log(error_message)
            yield "", chat_history
            return

    try:
        # Stream the bot's response
        ui_log(f"Starting stream for conversation {current_conversation_id}")
        response_stream = stream_message(api_base, api_key, current_conversation_id, user_message)
        # Buffer small token fragments and flush on boundaries (space, newline, punctuation)
        pending = ""
        flush_chars = set([" ", "\n", ".", "?", "!", ",", ":", ";", ")", "]", "}"])
        max_pending_len = 24
        for i, chunk in enumerate(response_stream):
            ui_log(f"Received stream chunk #{i}: '{chunk}'")
            # If a chunk begins with a debug JSON object (e.g. '{"debug":"stream-open"} ...'),
            # strip that leading object so we only show assistant text.
            m_lead = re.match(r'^\s*(\{[^}]*\bdebug\b[^}]*\})\s*(.*)$', chunk, flags=re.S)
            if m_lead:
                try:
                    maybe_obj = json.loads(m_lead.group(1))
                    if isinstance(maybe_obj, dict) and "debug" in maybe_obj:
                        stripped = m_lead.group(2) or ""
                        ui_log(f"Stripped leading debug object from chunk #{i}: {maybe_obj}")
                        chunk = stripped
                except Exception:
                    # If parsing fails, leave chunk unchanged
                    pass

            # Aggregate into pending and flush on boundaries to reduce flicker
            pending += chunk

            # Decide whether to flush pending buffer to the visible chat
            should_flush = False
            if not pending:
                should_flush = False
            else:
                # If pending ends with a flush character (space/newline/punct), flush
                if pending[-1] in flush_chars:
                    should_flush = True
                # Or if pending itself contains explicit paragraph markers
                elif "\n\n" in pending:
                    should_flush = True
                # Or if pending has grown too large
                elif len(pending) >= max_pending_len:
                    should_flush = True

            if should_flush:
                chat_history[-1]["content"] = _smart_append(chat_history[-1]["content"], pending)
                ui_log(f"Flushed pending buffer (len={len(pending)}): '{pending[:50]}'")
                pending = ""
                ui_log(f"Yielding history with flushed content at chunk {i}")
                yield "", chat_history

        # After stream ends, flush any remaining pending text
        if pending:
            chat_history[-1]["content"] = _smart_append(chat_history[-1]["content"], pending)
            ui_log(f"Flushed final pending buffer: '{pending[:50]}'")
            yield "", chat_history
    except requests.exceptions.RequestException as e:
        error_message = f"API Error: {e}"
        chat_history[-1]["content"] = error_message
        ui_log(error_message)
        yield "", chat_history
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        chat_history[-1]["content"] = error_message
        ui_log(error_message)
        yield "", chat_history
    
    ui_log("Bot response function finished.")


# --- Gradio UI Layout ---
with gr.Blocks() as demo:
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
    # Bind explicitly to localhost and disable public sharing to avoid
    # external origins (e.g. huggingface) being used by the frontend.
    # This prevents postMessage origin mismatches and manifest 404 errors
    # when running locally.
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, debug=True)