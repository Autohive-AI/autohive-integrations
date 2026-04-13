"""
Humanitix Integration for Autohive

This module provides retrieval functionality for events, orders, tickets, and tags.

All actions use the Humanitix Public API v1.
"""

from autohive_integrations_sdk import Integration


humanitix = Integration.load()

# Import actions to register handlers
from humanitix import actions  # noqa: F401, E402
