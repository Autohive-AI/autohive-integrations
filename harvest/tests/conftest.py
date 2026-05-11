import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Allow imports from the harvest package directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the platform OAuth shape Harvest expects."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "test_token",  # nosec B105
            "account_id": "test_account_id",
        },
    }
    return ctx
