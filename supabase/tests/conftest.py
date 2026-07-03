import pytest


@pytest.fixture
def mock_context(make_context):
    """Mock execution context with the wrapped Custom auth envelope Supabase expects."""
    return make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "host": "https://test.supabase.co",
                "service_role_secret": "test-service-role-secret",  # nosec B105
            },
        }
    )
