import pytest


@pytest.fixture
def mock_context(make_custom_auth_context):
    """Mock execution context with the wrapped Custom auth envelope Supabase expects.

    MagicMock attributes don't share state, so setting ``ctx.auth`` alone does
    not make the real ``credentials`` property available; set it explicitly to
    the unwrapped credentials dict.
    """
    credentials = {
        "host": "https://test.supabase.co",
        "service_role_secret": "test-service-role-secret",  # nosec B105
    }
    ctx = make_custom_auth_context(credentials)
    return ctx
