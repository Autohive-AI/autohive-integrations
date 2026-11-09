import pytest
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def live_auth(env_credentials):
    client_id = env_credentials("WORKZAPPY_CLIENT_ID")
    secret_key = env_credentials("WORKZAPPY_SECRET_KEY")
    if not client_id or not secret_key:
        pytest.skip("WORKZAPPY_CLIENT_ID and WORKZAPPY_SECRET_KEY are required")
    return ExecutionContext(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "client_id": client_id,
                "secret_key": secret_key,
            },
        }
    )
