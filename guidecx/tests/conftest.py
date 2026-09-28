import os
import sys

# The integration package directory is named "guidecx" and so is the module
# inside it (guidecx/guidecx.py), so the package shadows the module. Put the
# repo root on sys.path and import the module as `guidecx.guidecx`, matching
# the convention used by the other same-named integrations (trello, asana).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
