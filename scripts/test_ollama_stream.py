"""
A simple script to directly test the Ollama streaming client.
"""
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.ollama_client import generate_text_stream

async def main():
    """
    Main function to test the streaming generation.
    """
    prompt = "ai sản xuất chip"
    print(f"--- Testing Ollama stream with prompt: '{prompt}' ---")
    
    try:
        char_count = 0
        async for chunk in generate_text_stream(prompt):
            print(chunk, end="", flush=True)
            char_count += len(chunk)
        print("\n--- Stream finished ---")
        if char_count > 0:
            print(f"SUCCESS: Received {char_count} characters.")
        else:
            print("FAILURE: Stream ended but received no data.")
    except Exception as e:
        print(f"\n--- An error occurred ---")
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
