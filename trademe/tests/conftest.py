import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "consumer_key": "test-consumer",
            "consumer_secret": "test-consumer-secret",  # nosec B105 - mock credential
            "access_token": "test-token",  # nosec B105 - mock credential
            "access_token_secret": "test-token-secret",  # nosec B105 - mock credential
            "environment": "sandbox",
        },
    }
    return context
