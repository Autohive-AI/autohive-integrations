import os
import sys

# The integration folder is "linkedin-ads" (hyphen), which is not a valid
# Python package name, so it cannot be imported as a package. Put the
# integration directory itself on sys.path so `import linkedin_ads` resolves
# to linkedin_ads.py.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
