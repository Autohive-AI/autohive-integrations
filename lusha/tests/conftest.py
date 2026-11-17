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


@pytest.fixture
async def live_context(env_credentials):
    from autohive_integrations_sdk import ExecutionContext

    api_key = env_credentials("LUSHA_API_KEY")
    if not api_key:
        pytest.skip("LUSHA_API_KEY is not configured; connect the Lusha test account")
    async with ExecutionContext(auth={"auth_type": "Custom", "credentials": {"api_key": api_key}}) as context:
        yield context


@pytest.fixture
def paid_live_tests(env_credentials):
    if env_credentials("LUSHA_RUN_PAID_TESTS") != "1":
        pytest.skip("Set LUSHA_RUN_PAID_TESTS=1 to authorize credit-consuming live tests")


@pytest.fixture
def contact_identifier(env_credentials, paid_live_tests):
    contact_id = env_credentials("LUSHA_TEST_CONTACT_ID")
    email = env_credentials("LUSHA_TEST_CONTACT_EMAIL")
    if contact_id:
        return {"id": contact_id}
    if email:
        return {"email": email}
    pytest.skip("Configure a permitted dedicated-test contact using LUSHA_TEST_CONTACT_ID or LUSHA_TEST_CONTACT_EMAIL")


@pytest.fixture
def company_domain(env_credentials, paid_live_tests):
    domain = env_credentials("LUSHA_TEST_COMPANY_DOMAIN")
    if not domain:
        pytest.skip("LUSHA_TEST_COMPANY_DOMAIN is not configured")
    return domain


@pytest.fixture
def check_live_records():
    from autohive_integrations_sdk import ResultType

    def check(result):
        assert result.type == ResultType.ACTION, (
            "Lusha did not return an action result; inspect provider access and inputs"
        )
        data = result.result.data
        records = data.get("results")
        assert isinstance(records, list), "Expected a results array"
        assert bool(records), "The configured test input returned no records"
        if any(record.get("error", {}).get("code") == "COMPLIANCE_RESTRICTED" for record in records):
            pytest.skip("COMPLIANCE_RESTRICTED: configure a different permitted test contact; no retry was made")
        assert all(not record.get("error") for record in records), (
            "Provider returned a per-record error for the fixture"
        )
        return data, records

    return check
