"""
pytest configuration file.
"""

import sys
import os

# Add the agent module to the Python path so tests can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# You can add pytest fixtures, hooks, and other configuration here