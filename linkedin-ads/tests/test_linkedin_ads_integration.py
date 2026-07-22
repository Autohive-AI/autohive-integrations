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
    LINKEDIN_ADS_ACCESS_TOKEN   (required)
    LINKEDIN_ADS_TEST_ACCOUNT_ID (optional — otherwise the first accessible
                                  account is used)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, HTTPError

from linkedin_ads import (
    GetAdAccountsAction,
    GetCampaignsAction,
    GetCampaignAction,
    GetCampaignGroupsAction,
    GetCreativesAction,
    GetAdAnalyticsAction,
    GetAdAccountUsersAction,
    CreateCampaignAction,
    UpdateCampaignAction,
    PauseCampaignAction,
    ActivateCampaignAction,
)

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("LINKEDIN_ADS_ACCESS_TOKEN", "")
TEST_ACCOUNT_ID = os.environ.get("LINKEDIN_ADS_TEST_ACCOUNT_ID", "")


@pytest.fixture
def live_context():
    """Real ExecutionContext.fetch backed by aiohttp with Bearer auth.

    The integration relies on the SDK's platform-auth layer to inject the
    token in production; here we inject it manually. fetch receives the
    pre-encoded yarl.URL that make_request builds and forwards it verbatim,
    and raises HTTPError on non-2xx to mirror the real SDK.
    """
    if not ACCESS_TOKEN:
        pytest.skip("LINKEDIN_ADS_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                data = await resp.json(content_type=None)
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
    result = await GetAdAccountsAction().execute({}, live_context)
    accounts = result.data.get("accounts", [])
    if not accounts:
        pytest.skip("No ad accounts available for this token")
    return str(accounts[0]["id"])


# ---- Read-Only Tests ----


class TestGetAdAccounts:
    async def test_returns_accounts(self, live_context):
        result = await GetAdAccountsAction().execute({}, live_context)

        assert result.data["result"] is True
        assert isinstance(result.data["accounts"], list)

    async def test_respects_page_size(self, live_context):
        result = await GetAdAccountsAction().execute({"page_size": 1}, live_context)

        assert result.data["result"] is True
        assert len(result.data["accounts"]) <= 1


class TestGetAdAccountUsers:
    async def test_returns_users(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetAdAccountUsersAction().execute({"account_id": account_id}, live_context)

        assert result.data["result"] is True
        assert isinstance(result.data["users"], list)


class TestGetCampaigns:
    async def test_returns_campaigns(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetCampaignsAction().execute({"account_id": account_id}, live_context)

        assert result.data["result"] is True
        assert "campaigns" in result.data
        assert result.data["total"] == len(result.data["campaigns"])

    async def test_status_filter_accepted(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetCampaignsAction().execute({"account_id": account_id, "status": "ACTIVE"}, live_context)

        assert result.data["result"] is True


class TestGetCampaignGroups:
    async def test_returns_campaign_groups(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetCampaignGroupsAction().execute({"account_id": account_id}, live_context)

        assert result.data["result"] is True
        assert isinstance(result.data["campaign_groups"], list)


class TestGetCampaign:
    async def test_get_single_campaign(self, live_context):
        account_id = await resolve_account_id(live_context)

        listing = await GetCampaignsAction().execute({"account_id": account_id}, live_context)
        campaigns = listing.data.get("campaigns", [])
        if not campaigns:
            pytest.skip("No campaigns in the account to fetch")

        campaign_id = str(campaigns[0]["id"])
        result = await GetCampaignAction().execute({"account_id": account_id, "campaign_id": campaign_id}, live_context)

        assert result.data["result"] is True
        assert "campaign" in result.data

    async def test_nonexistent_campaign_returns_error(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetCampaignAction().execute({"account_id": account_id, "campaign_id": "999999999"}, live_context)

        # Path resolves; the campaign does not exist -> friendly not-found.
        assert result.data["result"] is False
        assert "not found" in result.data["error"].lower()


class TestGetCreatives:
    async def test_returns_creatives(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetCreativesAction().execute({"account_id": account_id}, live_context)

        assert result.data["result"] is True
        assert isinstance(result.data["creatives"], list)


class TestGetAdAnalytics:
    async def test_returns_analytics(self, live_context):
        account_id = await resolve_account_id(live_context)

        result = await GetAdAnalyticsAction().execute(
            {
                "account_id": account_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-30",
            },
            live_context,
        )

        assert result.data["result"] is True
        assert isinstance(result.data["analytics"], list)


# ---- Destructive Tests (Write Operations) ----
# These CREATE and MUTATE real campaigns on the connected account.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCampaignLifecycle:
    """create -> get -> update -> pause -> activate -> archive (cleanup).

    Exercises all four write actions end-to-end. There is no delete-campaign
    action in the LinkedIn API, so the campaign is archived at the end as the
    closest available cleanup. The campaign is created in DRAFT status.
    """

    async def test_full_lifecycle(self, live_context):
        account_id = await resolve_account_id(live_context)

        # A campaign group is required to create a campaign — grab one.
        groups = await GetCampaignGroupsAction().execute({"account_id": account_id}, live_context)
        group_list = groups.data.get("campaign_groups", [])
        if not group_list:
            pytest.skip("No campaign group available to create a campaign in")
        campaign_group_id = str(group_list[0]["id"])

        # Step 1: create_campaign (DRAFT)
        created = await CreateCampaignAction().execute(
            {
                "account_id": account_id,
                "campaign_group_id": campaign_group_id,
                "name": f"Autohive Integration Test {os.getpid()}",
                "objective_type": "WEBSITE_VISITS",
                "type": "SPONSORED_UPDATES",
                "daily_budget_amount": 10,
                "currency_code": "USD",
                "status": "DRAFT",
            },
            live_context,
        )
        assert created.data["result"] is True
        campaign_id = str(created.data["campaign_id"])
        assert campaign_id

        # Step 2: get_campaign — confirm it exists on the account-scoped path
        fetched = await GetCampaignAction().execute(
            {"account_id": account_id, "campaign_id": campaign_id}, live_context
        )
        assert fetched.data["result"] is True

        # Step 3: update_campaign — rename
        updated = await UpdateCampaignAction().execute(
            {"account_id": account_id, "campaign_id": campaign_id, "name": "Autohive Test (renamed)"},
            live_context,
        )
        assert updated.data["result"] is True

        # Step 4: pause_campaign
        paused = await PauseCampaignAction().execute(
            {"account_id": account_id, "campaign_id": campaign_id}, live_context
        )
        assert paused.data["result"] is True

        # Step 5: activate_campaign
        activated = await ActivateCampaignAction().execute(
            {"account_id": account_id, "campaign_id": campaign_id}, live_context
        )
        assert activated.data["result"] is True

        # Step 6: cleanup — archive (no delete action exists)
        await UpdateCampaignAction().execute(
            {"account_id": account_id, "campaign_id": campaign_id, "status": "ARCHIVED"},
            live_context,
        )
