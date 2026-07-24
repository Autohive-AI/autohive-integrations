"""
End-to-end integration tests for the LinkedIn Ads integration.

These call the real LinkedIn Marketing API (v202601) and require a valid
OAuth2 access token with the r_ads, r_ads_reporting, and rw_ads scopes in
the LINKEDIN_ADS_ACCESS_TOKEN environment variable (via .env or export).

Run read-only tests (safe — default):
    pytest linkedin-ads/tests/test_linkedin_ads_integration.py -m "integration and not destructive"

Run destructive tests (CREATE/UPDATE/PAUSE/ACTIVATE real campaigns — run
deliberately, never in CI, never by reviewers):
    pytest linkedin-ads/tests/test_linkedin_ads_integration.py -m "integration and destructive"

Never runs in CI: the default marker filter (-m unit) excludes these, and the
test_*_integration.py filename is not matched by python_files in pyproject.toml.

Environment variables (see root .env.example):
    LINKEDIN_ADS_ACCESS_TOKEN     (required)
    LINKEDIN_ADS_TEST_ACCOUNT_ID  (optional — otherwise the first accessible
                                   account is used)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType

from linkedin_ads import linkedin_ads

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("LINKEDIN_ADS_ACCESS_TOKEN", "")
TEST_ACCOUNT_ID = os.environ.get("LINKEDIN_ADS_TEST_ACCOUNT_ID", "")

skip_if_no_creds = pytest.mark.skipif(not ACCESS_TOKEN, reason="LINKEDIN_ADS_ACCESS_TOKEN required")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with a LinkedIn OAuth token.

    The integration relies on the SDK's platform-auth layer to inject the token
    in production; in tests we bypass it and add the Authorization header
    manually. fetch receives the pre-encoded yarl.URL built by li_fetch and
    forwards it verbatim, and raises HTTPError on non-2xx to mirror the SDK.
    """

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, body=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, data=body, headers=merged_headers, params=params
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},  # nosec B105
    }
    return ctx


async def resolve_account_id(live_context):
    """Return a usable ad account ID — the env override, else the first one."""
    if TEST_ACCOUNT_ID:
        return TEST_ACCOUNT_ID
    result = await linkedin_ads.execute_action("get_ad_accounts", {}, live_context)
    if result.type == ResultType.ACTION_ERROR:
        pytest.skip(f"could not list accounts: {result.result.message}")
    accounts = result.result.data.get("accounts", [])
    if not accounts:
        pytest.skip("No ad accounts available for this token")
    return str(accounts[0]["id"])


# ---- Read-Only Tests ----


@skip_if_no_creds
class TestGetAdAccounts:
    @pytest.mark.asyncio
    async def test_returns_accounts(self, live_context):
        result = await linkedin_ads.execute_action("get_ad_accounts", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["accounts"], list)

    @pytest.mark.asyncio
    async def test_respects_page_size(self, live_context):
        result = await linkedin_ads.execute_action("get_ad_accounts", {"page_size": 1}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert len(result.result.data["accounts"]) <= 1


@skip_if_no_creds
class TestGetAdAccountUsers:
    @pytest.mark.asyncio
    async def test_returns_users(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action("get_ad_account_users", {"account_id": account_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["users"], list)


@skip_if_no_creds
class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_returns_campaigns(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action("get_campaigns", {"account_id": account_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["campaigns"], list)

    @pytest.mark.asyncio
    async def test_status_filter_accepted(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action(
            "get_campaigns", {"account_id": account_id, "status": "ACTIVE"}, live_context
        )

        assert result.type == ResultType.ACTION, result.result


@skip_if_no_creds
class TestGetCampaignGroups:
    @pytest.mark.asyncio
    async def test_returns_campaign_groups(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action("get_campaign_groups", {"account_id": account_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["campaign_groups"], list)


@skip_if_no_creds
class TestGetCampaign:
    @pytest.mark.asyncio
    async def test_get_single_campaign(self, live_context):
        account_id = await resolve_account_id(live_context)

        listing = await linkedin_ads.execute_action("get_campaigns", {"account_id": account_id}, live_context)
        campaigns = listing.result.data.get("campaigns", [])
        if not campaigns:
            pytest.skip("No campaigns in the account to fetch")

        campaign_id = str(campaigns[0]["id"])
        result = await linkedin_ads.execute_action(
            "get_campaign", {"account_id": account_id, "campaign_id": campaign_id}, live_context
        )

        assert result.type == ResultType.ACTION, result.result
        assert "campaign" in result.result.data

    @pytest.mark.asyncio
    async def test_nonexistent_campaign_returns_error(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action(
            "get_campaign", {"account_id": account_id, "campaign_id": "999999999"}, live_context
        )

        # Path resolves; the campaign does not exist -> handler returns ActionError.
        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


@skip_if_no_creds
class TestGetCreatives:
    @pytest.mark.asyncio
    async def test_returns_creatives(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action("get_creatives", {"account_id": account_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["creatives"], list)


@skip_if_no_creds
class TestGetAdAnalytics:
    @pytest.mark.asyncio
    async def test_returns_analytics(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await linkedin_ads.execute_action(
            "get_ad_analytics",
            {"account_id": account_id, "start_date": "2026-06-01", "end_date": "2026-06-30"},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["analytics"], list)


# ---- Destructive Tests (Write Operations) ----
# These CREATE and MUTATE real campaigns on the connected account.
# Only run with: pytest -m "integration and destructive"


@skip_if_no_creds
@pytest.mark.destructive
class TestCampaignLifecycle:
    """create -> get -> update -> pause -> activate -> archive (cleanup).

    Exercises all four write actions end-to-end. There is no delete-campaign
    action in the LinkedIn API, so the campaign is archived at the end as the
    closest available cleanup. The campaign is created in DRAFT status.
    """

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        account_id = await resolve_account_id(live_context)

        groups = await linkedin_ads.execute_action("get_campaign_groups", {"account_id": account_id}, live_context)
        group_list = groups.result.data.get("campaign_groups", [])
        if not group_list:
            pytest.skip("No campaign group available to create a campaign in")
        campaign_group_id = str(group_list[0]["id"])

        # Step 1: create_campaign (DRAFT)
        created = await linkedin_ads.execute_action(
            "create_campaign",
            {
                "account_id": account_id,
                "campaign_group_id": campaign_group_id,
                "name": f"Autohive Integration Test {os.getpid()}",
                "objective_type": "WEBSITE_VISIT",
                "type": "SPONSORED_UPDATES",
                "daily_budget_amount": 10,
                "currency_code": "USD",
                "status": "DRAFT",
            },
            live_context,
        )
        assert created.type == ResultType.ACTION, created.result
        campaign_id = str(created.result.data["campaign_id"])
        assert campaign_id

        try:
            # Step 2: get_campaign
            fetched = await linkedin_ads.execute_action(
                "get_campaign", {"account_id": account_id, "campaign_id": campaign_id}, live_context
            )
            assert fetched.type == ResultType.ACTION, fetched.result

            # Step 3: update_campaign — rename
            updated = await linkedin_ads.execute_action(
                "update_campaign",
                {"account_id": account_id, "campaign_id": campaign_id, "name": "Autohive Test (renamed)"},
                live_context,
            )
            assert updated.type == ResultType.ACTION, updated.result

            # Step 4: pause_campaign
            paused = await linkedin_ads.execute_action(
                "pause_campaign", {"account_id": account_id, "campaign_id": campaign_id}, live_context
            )
            assert paused.type == ResultType.ACTION, paused.result

            # Step 5: activate_campaign
            activated = await linkedin_ads.execute_action(
                "activate_campaign", {"account_id": account_id, "campaign_id": campaign_id}, live_context
            )
            assert activated.type == ResultType.ACTION, activated.result
        finally:
            # Cleanup runs even if a step above fails, so no test campaign is
            # left behind. There is no delete action and the campaign is ACTIVE
            # by this point (LinkedIn only allows DELETE on DRAFT campaigns), so
            # archive is the correct terminal cleanup. Assert it succeeded.
            cleanup = await linkedin_ads.execute_action(
                "update_campaign",
                {"account_id": account_id, "campaign_id": campaign_id, "status": "ARCHIVED"},
                live_context,
            )
            assert cleanup.type == ResultType.ACTION, cleanup.result
