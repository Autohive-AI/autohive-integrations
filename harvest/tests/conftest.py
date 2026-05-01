import sys
import os

# Allow imports from the harvest package directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Allow 'from context import ...' to work when pytest runs from repo root
sys.path.insert(0, os.path.dirname(__file__))
