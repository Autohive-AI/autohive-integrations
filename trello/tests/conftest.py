import os
import sys

# Allow tests to import sibling test modules and the trello package
# regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
