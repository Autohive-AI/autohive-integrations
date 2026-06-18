import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "org_url": "https://testorg.crm.dynamics.com",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx
