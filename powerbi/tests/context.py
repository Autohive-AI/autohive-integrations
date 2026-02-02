"""
Test Context Module

This module sets up the necessary paths and imports for testing the Power BI integration.
It ensures that both the integration module and its dependencies are accessible to test files.
"""

import os
import sys

# Add parent directory to path so we can import the integration module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Add dependencies directory to path for third-party packages
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

# Import the Power BI integration instance
from powerbi import powerbi
