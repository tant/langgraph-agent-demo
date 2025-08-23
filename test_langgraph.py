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

Note: This is a helper script, not intended for pytest collection.
"""

import pytest  # type: ignore
import asyncio
from agent.langgraph_flow import test_flow

# Skip entire module when collected by pytest
pytestmark = pytest.mark.skip(reason="helper script; run directly via python to exercise the flow")

if __name__ == "__main__":
    print('Testing LangGraph flow...')
    asyncio.run(test_flow())
    print('Test passed!')