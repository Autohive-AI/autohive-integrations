import os
import sys

# Add parent directory to path to import clickup module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clickup import clickup
