import os
import sys

# Put repo root on sys.path so `whatsapp` resolves as a package (whatsapp/__init__.py),
# allowing `from whatsapp.whatsapp import ...` in the test modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
