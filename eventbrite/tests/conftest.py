import os
import sys

# Add the repo root to sys.path so the integration is importable as the
# ``eventbrite`` package (eventbrite/__init__.py re-exports the integration).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
