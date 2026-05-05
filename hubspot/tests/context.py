# -*- coding: utf-8 -*-
"""Test import setup: chdir to integration root and expose the loaded integration."""

import importlib.util
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.abspath(os.path.join(parent_dir, "dependencies")))

_spec = importlib.util.spec_from_file_location("hubspot_mod", os.path.join(parent_dir, "hubspot.py"))
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
hubspot = _mod.hubspot  # noqa: F401 — re-export for `from context import hubspot`
