"""Test conftest for the Google Forms integration.

Adds ``google-forms/`` to ``sys.path`` so ``from google_forms import google_forms``
resolves. The directory name is hyphenated, so it isn't a regular Python
package — we add the dir itself to ``sys.path`` to make the inner
``google_forms.py`` module importable by name.

Also overrides the repo-wide ``mock_context`` fixture so every test in this
directory automatically inherits the platform-OAuth shape the integration's
``build_credentials`` expects.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context() -> MagicMock:
    """Mock ExecutionContext pre-loaded with platform-OAuth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_access_token"},  # nosec B105
    }
    return ctx
