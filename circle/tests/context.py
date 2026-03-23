# -*- coding: utf-8 -*-
import sys
import os

# Add parent directory and dependencies to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

from autohive_integrations_sdk import Integration

# Monkey patch Integration.load to fix test execution environment issue
# This ensures config.json is found relative to the test runner
_original_load = Integration.load

def _mock_load(path=None):
    if path is None:
        # Check if config.json exists in the current working directory or parent
        possible_path = os.path.abspath("config.json")
        if os.path.exists(possible_path):
            path = possible_path
    return _original_load(path)

Integration.load = _mock_load

from circle import circle