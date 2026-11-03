import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from autohive_integrations_sdk import ExecutionContext  # noqa: E402


@pytest.fixture
def sql_context():
    """Factory for a mock context with the integration's custom auth fields."""

    def _factory(database_type: str, connection_string: str, **settings: str) -> MagicMock:
        ctx = MagicMock(spec=ExecutionContext)
        ctx.auth = {
            "auth_type": "Custom",
            "credentials": {"database_type": database_type, "connection_string": connection_string, **settings},
        }
        return ctx

    return _factory


@pytest.fixture
def mock_context(sql_context):
    return sql_context(
        "sqlserver",
        "Server=tcp:db.example.com,1433;Database=app;User ID=reader;Password=test-only;Encrypt=True",
        access_mode="read-write",
    )
