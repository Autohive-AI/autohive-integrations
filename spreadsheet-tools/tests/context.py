"""
Test context configuration for Spreadsheet Tools integration tests.

Sets up Python path to enable imports from parent directories,
allowing tests to access the spreadsheet_tools module and dependencies.
"""
# -*- coding: utf-8 -*-
import sys
import os

# Add parent directories to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

# Import the integration instance
from spreadsheet_tools import spreadsheet_tools
