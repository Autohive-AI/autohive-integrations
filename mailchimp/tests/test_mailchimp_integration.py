"""
End-to-end integration tests for the Mailchimp integration.

These tests call the real Mailchimp API and require a valid access token
and data center code set in environment variables (via .env or export).

Run read-only tests (safe to run repeatedly):
    pytest mailchimp/tests/test_mailchimp_integration.py -m "integration and not destructive"

Run destructive tests (creates real data — lists, members, campaigns):
    pytest mailchimp/tests/test_mailchimp_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("mailchimp_mod", os.path.join(_parent, "mailchimp.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

import aiohttp  # noqa: E402
import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

mailchimp = _mod.mailchimp
MailchimpConnectedAccountHandler = _mod.MailchimpConnectedAccountHandler

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("MAILCHIMP_ACCESS_TOKEN", "")
DC = os.environ.get("MAILCHIMP_DC", "")
TEST_LIST_ID = os.environ.get("MAILCHIMP_TEST_LIST_ID", "")
TEST_CAMPAIGN_ID = os.environ.get("MAILCHIMP_TEST_CAMPAIGN_ID", "")


def require_test_list_id():
    if not TEST_LIST_ID:
        pytest.skip("MAILCHIMP_TEST_LIST_ID not set — skipping test")


def require_test_campaign_id():
    if not TEST_CAMPAIGN_ID:
        pytest.skip("MAILCHIMP_TEST_CAMPAIGN_ID not set — skipping test")


@pytest.fixture
def live_context(env_credentials):
    access_token = env_credentials("MAILCHIMP_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("MAILCHIMP_ACCESS_TOKEN not set — skipping integration tests")

    dc = env_credentials("MAILCHIMP_DC")
    if not dc:
        pytest.skip("MAILCHIMP_DC not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": access_token},
    }
    ctx.metadata = {"dc": dc}
    return ctx


# =============================================================================
# CONNECTED ACCOUNT
# =============================================================================


class TestConnectedAccount:
    async def test_returns_username(self, live_context):
        handler = MailchimpConnectedAccountHandler()
        result = await handler.get_account_info(live_context)
        assert result.username is not None
        assert result.user_id is not None

    async def test_returns_organization(self, live_context):
        handler = MailchimpConnectedAccountHandler()
        result = await handler.get_account_info(live_context)
        assert result.organization is not None


# =============================================================================
# GET LISTS
# =============================================================================


class TestGetLists:
    async def test_returns_lists_array(self, live_context):
        result = await mailchimp.execute_action("get_lists", {}, live_context)
        data = result.result.data
        assert "lists" in data
        assert isinstance(data["lists"], list)
        assert "total_items" in data

    async def test_limit_respected(self, live_context):
        result = await mailchimp.execute_action("get_lists", {"count": 1}, live_context)
        assert len(result.result.data["lists"]) <= 1

    async def test_list_item_has_expected_fields(self, live_context):
        result = await mailchimp.execute_action("get_lists", {"count": 1}, live_context)
        lists = result.result.data["lists"]
        if not lists:
            pytest.skip("No lists in this Mailchimp account")
        lst = lists[0]
        assert "id" in lst
        assert "name" in lst


# =============================================================================
# FIND LIST
# =============================================================================


class TestFindList:
    async def test_finds_existing_list(self, live_context):
        lists_result = await mailchimp.execute_action("get_lists", {"count": 1}, live_context)
        lists = lists_result.result.data["lists"]
        if not lists:
            pytest.skip("No lists in this Mailchimp account")

        first_list_name = lists[0]["name"]
        partial_name = first_list_name[:3]

        result = await mailchimp.execute_action("find_list", {"name": partial_name}, live_context)
        assert result.result.data["result"] is True
        assert "list" in result.result.data

    async def test_not_found_returns_action_error(self, live_context):
        result = await mailchimp.execute_action(
            "find_list",
            {"name": "zzz_nonexistent_list_xyz_999"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET LIST
# =============================================================================


class TestGetList:
    async def test_returns_list_details(self, live_context):
        require_test_list_id()
        result = await mailchimp.execute_action("get_list", {"list_id": TEST_LIST_ID}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "list" in data
        assert data["list"]["id"] == TEST_LIST_ID

    async def test_list_has_expected_fields(self, live_context):
        require_test_list_id()
        result = await mailchimp.execute_action("get_list", {"list_id": TEST_LIST_ID}, live_context)
        lst = result.result.data["list"]
        assert "id" in lst
        assert "name" in lst

    async def test_chains_from_get_lists(self, live_context):
        lists_result = await mailchimp.execute_action("get_lists", {"count": 1}, live_context)
        lists = lists_result.result.data["lists"]
        if not lists:
            pytest.skip("No lists in this Mailchimp account")

        list_id = lists[0]["id"]
        result = await mailchimp.execute_action("get_list", {"list_id": list_id}, live_context)
        assert result.result.data["list"]["id"] == list_id


# =============================================================================
# GET LIST MEMBERS
# =============================================================================


class TestGetListMembers:
    async def test_returns_members_array(self, live_context):
        require_test_list_id()
        result = await mailchimp.execute_action("get_list_members", {"list_id": TEST_LIST_ID, "count": 5}, live_context)
        data = result.result.data
        assert "members" in data
        assert isinstance(data["members"], list)
        assert "total_items" in data

    async def test_count_respected(self, live_context):
        require_test_list_id()
        result = await mailchimp.execute_action("get_list_members", {"list_id": TEST_LIST_ID, "count": 2}, live_context)
        assert len(result.result.data["members"]) <= 2

    async def test_status_filter_applied(self, live_context):
        require_test_list_id()
        result = await mailchimp.execute_action(
            "get_list_members",
            {"list_id": TEST_LIST_ID, "status": "subscribed", "count": 5},
            live_context,
        )
        members = result.result.data["members"]
        for member in members:
            assert member.get("status") == "subscribed"


# =============================================================================
# GET MEMBER
# =============================================================================


class TestGetMember:
    async def test_retrieves_member_by_email(self, live_context):
        require_test_list_id()
        members_result = await mailchimp.execute_action(
            "get_list_members", {"list_id": TEST_LIST_ID, "count": 1}, live_context
        )
        members = members_result.result.data["members"]
        if not members:
            pytest.skip("No members in the test list")

        email = members[0]["email_address"]
        result = await mailchimp.execute_action(
            "get_member", {"list_id": TEST_LIST_ID, "email_address": email}, live_context
        )
        data = result.result.data
        assert data["result"] is True
        assert data["member"]["email_address"] == email

    async def test_member_has_expected_fields(self, live_context):
        require_test_list_id()
        members_result = await mailchimp.execute_action(
            "get_list_members", {"list_id": TEST_LIST_ID, "count": 1}, live_context
        )
        members = members_result.result.data["members"]
        if not members:
            pytest.skip("No members in the test list")

        email = members[0]["email_address"]
        result = await mailchimp.execute_action(
            "get_member", {"list_id": TEST_LIST_ID, "email_address": email}, live_context
        )
        member = result.result.data["member"]
        assert "id" in member
        assert "email_address" in member
        assert "status" in member
        assert "merge_fields" in member


# =============================================================================
# GET CAMPAIGNS
# =============================================================================


class TestGetCampaigns:
    async def test_returns_campaigns_array(self, live_context):
        result = await mailchimp.execute_action("get_campaigns", {}, live_context)
        data = result.result.data
        assert "campaigns" in data
        assert isinstance(data["campaigns"], list)
        assert "total_items" in data

    async def test_limit_respected(self, live_context):
        result = await mailchimp.execute_action("get_campaigns", {"count": 2}, live_context)
        assert len(result.result.data["campaigns"]) <= 2

    async def test_campaign_item_has_expected_fields(self, live_context):
        result = await mailchimp.execute_action("get_campaigns", {"count": 1}, live_context)
        campaigns = result.result.data["campaigns"]
        if not campaigns:
            pytest.skip("No campaigns in this Mailchimp account")
        cmp = campaigns[0]
        assert "id" in cmp
        assert "type" in cmp
        assert "status" in cmp


# =============================================================================
# FIND CAMPAIGN
# =============================================================================


class TestFindCampaign:
    async def test_finds_existing_campaign(self, live_context):
        campaigns_result = await mailchimp.execute_action("get_campaigns", {"count": 1}, live_context)
        campaigns = campaigns_result.result.data["campaigns"]
        if not campaigns:
            pytest.skip("No campaigns in this Mailchimp account")

        settings = campaigns[0].get("settings", {})
        title = settings.get("title", "") or settings.get("subject_line", "")
        if not title:
            pytest.skip("Campaign has no title or subject line to search by")

        result = await mailchimp.execute_action("find_campaign", {"query": title[:5]}, live_context)
        assert result.result.data["result"] is True

    async def test_not_found_returns_action_error(self, live_context):
        result = await mailchimp.execute_action(
            "find_campaign",
            {"query": "zzz_nonexistent_campaign_xyz_999"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET CAMPAIGN
# =============================================================================


class TestGetCampaign:
    async def test_returns_campaign_details(self, live_context):
        require_test_campaign_id()
        result = await mailchimp.execute_action("get_campaign", {"campaign_id": TEST_CAMPAIGN_ID}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "campaign" in data
        assert data["campaign"]["id"] == TEST_CAMPAIGN_ID

    async def test_chains_from_get_campaigns(self, live_context):
        campaigns_result = await mailchimp.execute_action("get_campaigns", {"count": 1}, live_context)
        campaigns = campaigns_result.result.data["campaigns"]
        if not campaigns:
            pytest.skip("No campaigns in this Mailchimp account")

        campaign_id = campaigns[0]["id"]
        result = await mailchimp.execute_action("get_campaign", {"campaign_id": campaign_id}, live_context)
        assert result.result.data["campaign"]["id"] == campaign_id


# =============================================================================
# DESTRUCTIVE TESTS — create/write real data
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestMemberLifecycle:
    """Add → update a test member in a list.

    Requires MAILCHIMP_TEST_LIST_ID to be set.
    Note: Mailchimp does not offer a delete-member API endpoint, so the test
    member persists as 'unsubscribed' after the test. Clean up manually in
    the Mailchimp dashboard if needed.
    """

    async def test_add_and_update_member(self, live_context):
        require_test_list_id()

        test_email = f"autohive-test-{os.getpid()}@example.com"

        # Add member
        add_result = await mailchimp.execute_action(
            "add_member",
            {
                "list_id": TEST_LIST_ID,
                "email_address": test_email,
                "status": "subscribed",
                "merge_fields": {"FNAME": "Integration", "LNAME": "Test"},
            },
            live_context,
        )
        assert add_result.result.data["result"] is True
        assert add_result.result.data["member"]["email_address"] == test_email

        # Update member — change merge fields
        update_result = await mailchimp.execute_action(
            "update_member",
            {
                "list_id": TEST_LIST_ID,
                "email_address": test_email,
                "merge_fields": {"FNAME": "Updated", "LNAME": "Test"},
            },
            live_context,
        )
        assert update_result.result.data["result"] is True

        # Unsubscribe to clean up (Mailchimp has no delete member endpoint)
        await mailchimp.execute_action(
            "update_member",
            {"list_id": TEST_LIST_ID, "email_address": test_email, "status": "unsubscribed"},
            live_context,
        )


@pytest.mark.destructive
class TestCreateList:
    """Creates a new mailing list.

    Note: Mailchimp has no delete-list action, so the created list persists.
    Clean up manually in the Mailchimp dashboard after running this test.
    """

    async def test_creates_new_list(self, live_context):
        result = await mailchimp.execute_action(
            "create_list",
            {
                "name": f"Autohive Integration Test {os.getpid()}",
                "permission_reminder": "You signed up for our integration tests.",
                "contact": {
                    "company": "Autohive",
                    "address1": "123 Test St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94105",
                    "country": "US",
                },
                "campaign_defaults": {
                    "from_name": "Autohive Test",
                    "from_email": "test@autohive.com",
                    "subject": "Test",
                    "language": "en",
                },
            },
            live_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert "list" in data
        assert data["list"]["id"] is not None


@pytest.mark.destructive
class TestCreateCampaign:
    """Creates a draft campaign.

    Requires MAILCHIMP_TEST_LIST_ID to be set.
    Note: The created campaign remains as a draft in the account.
    Delete it manually in the Mailchimp dashboard after running this test.
    """

    async def test_creates_draft_campaign(self, live_context):
        require_test_list_id()

        result = await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": TEST_LIST_ID,
                "subject_line": f"Autohive Integration Test {os.getpid()}",
                "from_name": "Autohive Test",
                "reply_to": "test@autohive.com",
                "title": f"Autohive Integration Test Campaign {os.getpid()}",
            },
            live_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["campaign"]["id"] is not None
        assert data["campaign"]["status"] == "save"
