import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "test_access_token",  # nosec B105
        },
    }
    context.metadata = {"api": "https://au-api.jobadder.com/v2"}
    return context
