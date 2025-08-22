# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "langgraph",
#     "sqlalchemy[asyncio]>=2.0.0",
#     "aiosqlite",
#     "chromadb",
#     "requests",
# ]
# ///
"""
Test script for the LangGraph flow.
"""

import asyncio
from agent.langgraph_flow import test_flow

if __name__ == "__main__":
    print('Testing LangGraph flow...')
    asyncio.run(test_flow())
    print('Test passed!')