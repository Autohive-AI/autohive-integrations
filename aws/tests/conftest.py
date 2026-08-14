import pytest
from unittest.mock import MagicMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",  # nosec B105
            "aws_region": "us-east-1",
        },
    }
    return ctx
