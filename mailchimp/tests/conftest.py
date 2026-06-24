"""Test configuration for the Mailchimp integration.

Shared fixtures (``mock_context``, etc.) come from the repository-root
``conftest.py``. Tests import the integration via the package path
(``from mailchimp.mailchimp import ...``), which resolves from the repo root
that pytest puts on ``sys.path``.

Do NOT insert the integration directory onto ``sys.path`` here: that makes
``mailchimp.py`` importable as a top-level module and shadows the ``mailchimp``
package, breaking the package-style imports during collection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_context():
    """Mock ExecutionContext with Platform OAuth shape and Mailchimp dc metadata."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    ctx.metadata = {"dc": "us19"}
    return ctx
