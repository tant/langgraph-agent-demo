# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "chromadb",
# ]
# ///
"""
Test script for the retriever module.
"""

from agent.retriever import test_query_and_rerank

if __name__ == "__main__":
    print('Testing query and re-rank...')
    test_query_and_rerank()
    print('Test passed!')