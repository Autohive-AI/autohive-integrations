"""
Facebook Pages Integration for Autohive

This module provides comprehensive Facebook Pages management including:
- Page discovery and listing
- Post creation (text, photo, video, links) with scheduling
- Post retrieval and deletion
- Comment management (read, reply, hide, delete)
- Page and post insights/analytics

All actions use the Facebook Graph API v21.0.
"""

from autohive_integrations_sdk import Integration
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
facebook = Integration.load(config_path)

# Import actions to register handlers
import actions
