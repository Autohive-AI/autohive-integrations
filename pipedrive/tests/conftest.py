import os
import sys

# Add the repo root to sys.path so the integration is importable as the
# ``pipedrive`` package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
