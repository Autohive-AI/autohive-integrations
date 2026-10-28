import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with Retail Express custom auth credentials."""
    context = MagicMock(name="ExecutionContext")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {"api_key": "test-api-key"},  # nosec B105
    }
    context.fetch = AsyncMock(name="fetch")
    return context
