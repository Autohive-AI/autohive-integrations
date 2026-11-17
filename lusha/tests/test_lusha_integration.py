"""Live account and Waterfall job checks. Job testing requires a real job ID."""

import pytest
from autohive_integrations_sdk import ResultType

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


async def test_get_account_usage(live_context):
    result = await lusha.execute_action("get_account_usage", {}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data.get("credits"), dict)
    assert isinstance(data["credits"].get("remaining"), (int, float))
    for key in ("rateLimits", "plan", "pricing"):
        assert isinstance(data.get(key), dict)


async def test_get_contact_enrichment_job(live_context, env_credentials):
    job_id = env_credentials("LUSHA_TEST_ENRICHMENT_JOB_ID")
    if not job_id:
        pytest.skip("No real Waterfall job ID configured; this requires an entitled plan and an unexpired job")
    result = await lusha.execute_action("get_contact_enrichment_job", {"job_id": job_id}, live_context)
    assert result.type == ResultType.ACTION, "The configured job could not be read; check its account and expiry"
    data = result.result.data
    assert data["jobId"] == job_id
    assert isinstance(data["requestId"], str)
    assert isinstance(data["expiresAt"], str)
    assert data["status"] in {"processing", "complete", "expired", "failed"}
    if data["status"] == "processing":
        assert isinstance(data.get("retryAfter"), (int, float))
        assert data["retryAfter"] >= 0
    else:
        assert isinstance(data.get("contacts", []), list)
