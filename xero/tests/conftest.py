import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Allow direct imports from the integration package when pytest runs from the
# repository root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the platform OAuth shape Xero expects."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "test_token",  # nosec B105
            "tenant_id": "test_tenant",
        },
    }
    return ctx
