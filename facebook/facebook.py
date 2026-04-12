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


facebook = Integration.load()

# Import actions to register handlers
from facebook import comments, insights, pages, posts  # noqa: F401, E402
