import os
import sys

# Put the integration root on sys.path so test files can use plain imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
