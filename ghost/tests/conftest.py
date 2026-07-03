import pytest


@pytest.fixture
def mock_context(make_custom_auth_context):
    credentials = {
        "api_url": "https://demo.ghost.io",
        "content_api_key": "test_content_key",  # nosec B105
        "admin_api_key": "testid00000000000000000a:aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",  # nosec B105
    }
    ctx = make_custom_auth_context(credentials)
    return ctx
