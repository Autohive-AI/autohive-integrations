"""
Humanitix Integration for Autohive

This module provides retrieval functionality for events, orders, tickets, and tags.

All actions use the Humanitix Public API v1.
"""

from autohive_integrations_sdk import Integration
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
humanitix = Integration.load(config_path)

# Import actions to register handlers
import actions
