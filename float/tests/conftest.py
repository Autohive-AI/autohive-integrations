import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(_parent)
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["float_mod"] = _mod
