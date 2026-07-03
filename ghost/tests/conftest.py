import pytest

# 32-byte hex secret keeps PyJWT's HS256 key-length warning quiet.
_ADMIN_API_KEY = "testid00000000000000000a:" + "aabbccddeeff0011" * 4  # nosec B105


@pytest.fixture
def mock_context(make_context):
    """Mock execution context with the wrapped Custom auth envelope Ghost expects."""
    return make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "api_url": "https://demo.ghost.io",
                "content_api_key": "test_content_key",  # nosec B105
                "admin_api_key": _ADMIN_API_KEY,
            },
        }
    )
