"""Shared pytest setup for the Dropbox integration tests.

Adds the integration directory to ``sys.path`` so test files can import the
integration module with ``from dropbox import dropbox`` and overrides the
repo-wide ``mock_context`` with the PlatformOauth2 credentials shape Dropbox
expects.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make dropbox.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with Dropbox PlatformOauth2 credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx
