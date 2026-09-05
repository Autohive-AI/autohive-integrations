import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with this integration's credentials."""
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {"auth_type": "Custom", "credentials": {"api_key": "test-key"}}  # nosec B105
    return context
