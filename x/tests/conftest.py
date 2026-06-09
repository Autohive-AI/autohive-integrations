import os
import sys

# Make x.py importable as a top-level module (`import x`).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
