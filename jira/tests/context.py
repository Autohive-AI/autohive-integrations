import sys
import os

# Add the integration directory to the path so tests can import jira.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
