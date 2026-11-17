import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.config = {"max_retries": 3, "timeout": 30}
    context.auth = {"auth_type": "Custom", "credentials": {"api_key": "test-api-key"}}  # nosec B105
    return context
