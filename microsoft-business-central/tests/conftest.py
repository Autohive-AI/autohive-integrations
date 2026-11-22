import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test-token"}}  # nosec B105
    context.fetch = AsyncMock()
    return context
