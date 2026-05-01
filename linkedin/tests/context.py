"""Path setup + re-exports for the unit tests.

Loads `linkedin.py` directly via importlib so we don't collide with the
`linkedin/` package's empty `__init__.py` when pytest runs from the repo root.
"""

import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

_spec = importlib.util.spec_from_file_location("linkedin_mod", os.path.join(_parent, "linkedin.py"))
linkedin_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(linkedin_module)

# The Integration instance the tests call execute_action on.
linkedin = linkedin_module.linkedin
