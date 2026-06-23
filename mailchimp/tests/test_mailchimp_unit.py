"""
Unit tests for the Mailchimp integration using mocked fetch.
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("mailchimp_mod", os.path.join(_parent, "mailchimp.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

mailchimp = _mod.mailchimp
MailchimpRateLimiter = _mod.MailchimpRateLimiter
MailchimpRateLimitException = _mod.MailchimpRateLimitException
get_mailchimp_base_url = _mod.get_mailchimp_base_url
get_data_center = _mod.get_data_center
get_subscriber_hash = _mod.get_subscriber_hash
MailchimpConnectedAccountHandler = _mod.MailchimpConnectedAccountHandler

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


# =============================================================================
# HELPERS
# =============================================================================


class TestGetMailchimpBaseUrl:
    def test_builds_correct_url(self):
        assert get_mailchimp_base_url("us19") == "https://us19.api.mailchimp.com/3.0"

    def test_different_dc(self):
        assert get_mailchimp_base_url("us1") == "https://us1.api.mailchimp.com/3.0"


class TestGetSubscriberHash:
    def test_md5_of_lowercase_email(self):
        result = get_subscriber_hash("Test@Example.COM")
        # md5 of "test@example.com"
        assert result == "55502f40dc8b7c769880b10874abc9d0"

    def test_already_lowercase(self):
        result = get_subscriber_hash("user@domain.com")
        assert len(result) == 32
        assert result == get_subscriber_hash("USER@DOMAIN.COM")


class TestGetDataCenter:
    def test_returns_dc_from_metadata(self):
        ctx = MagicMock()
        ctx.metadata = {"dc": "us6"}
        assert get_data_center(ctx) == "us6"

    def test_raises_when_metadata_missing_dc(self):
        ctx = MagicMock()
        ctx.metadata = {}
        with pytest.raises(ValueError, match="data center"):
            get_data_center(ctx)

    def test_raises_when_no_metadata(self):
        ctx = MagicMock(spec=[])  # no metadata attribute
        with pytest.raises(ValueError, match="data center"):
            get_data_center(ctx)


# =============================================================================
# RATE LIMITER
# =============================================================================


class TestMailchimpRateLimiter:
    @pytest.mark.asyncio
    async def test_returns_response_data_on_success(self, mock_context):
        limiter = MailchimpRateLimiter()
        mock_context.fetch.return_value = ok({"lists": [{"id": "abc"}]})
        result = await limiter.make_request(mock_context, "https://us19.api.mailchimp.com/3.0/lists")
        assert result == {"lists": [{"id": "abc"}]}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_429_status(self, mock_sleep, mock_context):
        limiter = MailchimpRateLimiter(default_retry_delay=1, max_retries=1)
        mock_context.fetch.side_effect = [
            FetchResponse(status=429, headers={}, data={}),
            ok({"lists": []}),
        ]
        result = await limiter.make_request(mock_context, "https://example.com/lists")
        assert result == {"lists": []}
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_raises_after_max_retries_on_429(self, mock_sleep, mock_context):
        limiter = MailchimpRateLimiter(default_retry_delay=1, max_retries=1)
        mock_context.fetch.return_value = FetchResponse(status=429, headers={}, data={})
        with pytest.raises(MailchimpRateLimitException):
            await limiter.make_request(mock_context, "https://example.com/lists")

    @pytest.mark.asyncio
    async def test_uses_retry_after_header(self, mock_context):
        limiter = MailchimpRateLimiter(default_retry_delay=60, max_retries=0)
        mock_context.fetch.return_value = FetchResponse(status=429, headers={"Retry-After": "30"}, data={})
        with pytest.raises(MailchimpRateLimitException) as exc_info:
            await limiter.make_request(mock_context, "https://example.com/lists")
        assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_non_rate_limit_exception_reraises(self, mock_context):
        limiter = MailchimpRateLimiter()
        mock_context.fetch.side_effect = Exception("Connection refused")
        with pytest.raises(Exception, match="Connection refused"):
            await limiter.make_request(mock_context, "https://example.com/lists")

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_string_based_429_fallback(self, mock_sleep, mock_context):
        limiter = MailchimpRateLimiter(default_retry_delay=1, max_retries=0)
        mock_context.fetch.side_effect = Exception("HTTP 429: Too Many Requests")
        with pytest.raises(MailchimpRateLimitException):
            await limiter.make_request(mock_context, "https://example.com/lists")

    def test_extract_retry_delay_uses_default_when_header_missing(self):
        limiter = MailchimpRateLimiter(default_retry_delay=45)
        response = FetchResponse(status=429, headers={}, data={})
        assert limiter._extract_retry_delay(response) == 45

    def test_extract_retry_delay_uses_default_when_header_invalid(self):
        limiter = MailchimpRateLimiter(default_retry_delay=45)
        response = FetchResponse(status=429, headers={"Retry-After": "not-a-number"}, data={})
        assert limiter._extract_retry_delay(response) == 45


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


class TestConnectedAccountHandler:
    @pytest.mark.asyncio
    async def test_returns_account_info(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "account_id": "abc123",
                "account_name": "Acme Corp",
                "email": "owner@acme.com",
                "username": "acmeuser",
                "first_name": "Jane",
                "last_name": "Doe",
            }
        )
        handler = MailchimpConnectedAccountHandler()
        result = await handler.get_account_info(mock_context)
        assert result.email == "owner@acme.com"
        assert result.username == "acmeuser"
        assert result.first_name == "Jane"
        assert result.last_name == "Doe"
        assert result.organization == "Acme Corp"
        assert result.user_id == "abc123"

    @pytest.mark.asyncio
    async def test_uses_login_name_when_username_absent(self, mock_context):
        mock_context.fetch.return_value = ok({"account_id": "x", "login_name": "loginuser"})
        handler = MailchimpConnectedAccountHandler()
        result = await handler.get_account_info(mock_context)
        assert result.username == "loginuser"

    @pytest.mark.asyncio
    async def test_calls_root_endpoint(self, mock_context):
        mock_context.fetch.return_value = ok({"account_id": "x"})
        handler = MailchimpConnectedAccountHandler()
        await handler.get_account_info(mock_context)
        url = mock_context.fetch.call_args.args[0]
        assert "us19.api.mailchimp.com/3.0/" in url

    @pytest.mark.asyncio
    async def test_raises_on_fetch_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API down")
        handler = MailchimpConnectedAccountHandler()
        with pytest.raises(Exception, match="Failed to fetch Mailchimp account info"):
            await handler.get_account_info(mock_context)

    @pytest.mark.asyncio
    async def test_raises_when_dc_missing(self):
        ctx = MagicMock(name="ExecutionContext")
        ctx.fetch = AsyncMock()
        ctx.metadata = {}  # no dc key
        handler = MailchimpConnectedAccountHandler()
        with pytest.raises(Exception, match="Failed to fetch Mailchimp account info"):
            await handler.get_account_info(ctx)


# =============================================================================
# GET LISTS
# =============================================================================


SAMPLE_LIST = {"id": "abc123", "name": "Newsletter", "stats": {"member_count": 500}}


class TestGetLists:
    @pytest.mark.asyncio
    async def test_returns_lists(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [SAMPLE_LIST], "total_items": 1})
        result = await mailchimp.execute_action("get_lists", {}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert len(data["lists"]) == 1
        assert data["lists"][0]["id"] == "abc123"
        assert data["total_items"] == 1

    @pytest.mark.asyncio
    async def test_empty_lists(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [], "total_items": 0})
        result = await mailchimp.execute_action("get_lists", {}, mock_context)
        assert result.result.data["lists"] == []
        assert result.result.data["total_items"] == 0

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [], "total_items": 0})
        await mailchimp.execute_action("get_lists", {}, mock_context)
        url = mock_context.fetch.call_args.args[0]
        assert "us19.api.mailchimp.com/3.0/lists" in url
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [], "total_items": 0})
        await mailchimp.execute_action("get_lists", {"count": 25, "offset": 50}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == 25
        assert params["offset"] == 50

    @pytest.mark.asyncio
    async def test_default_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [], "total_items": 0})
        await mailchimp.execute_action("get_lists", {}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == 10
        assert params["offset"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")
        result = await mailchimp.execute_action("get_lists", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_rate_limit_returns_action_error(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=429, headers={"Retry-After": "5"}, data={})
        result = await mailchimp.execute_action("get_lists", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Rate limit" in result.result.message
        assert "5" in result.result.message


# =============================================================================
# FIND LIST
# =============================================================================


class TestFindList:
    @pytest.mark.asyncio
    async def test_finds_matching_list(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"lists": [{"id": "a1", "name": "Newsletter"}, {"id": "b2", "name": "Promotions"}]}
        )
        result = await mailchimp.execute_action("find_list", {"name": "news"}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["list"]["id"] == "a1"

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [{"id": "x1", "name": "Weekly DIGEST"}]})
        result = await mailchimp.execute_action("find_list", {"name": "weekly digest"}, mock_context)
        assert result.result.data["list"]["id"] == "x1"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": [{"id": "a1", "name": "Newsletter"}]})
        result = await mailchimp.execute_action("find_list", {"name": "nonexistent"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "nonexistent" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")
        result = await mailchimp.execute_action("find_list", {"name": "test"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_fetches_with_count_100(self, mock_context):
        mock_context.fetch.return_value = ok({"lists": []})
        await mailchimp.execute_action("find_list", {"name": "x"}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == 100


# =============================================================================
# GET LIST
# =============================================================================


class TestGetList:
    @pytest.mark.asyncio
    async def test_returns_list_details(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "list123", "name": "My List", "stats": {}})
        result = await mailchimp.execute_action("get_list", {"list_id": "list123"}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert data["list"]["id"] == "list123"

    @pytest.mark.asyncio
    async def test_request_includes_list_id_in_url(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "list123"})
        await mailchimp.execute_action("get_list", {"list_id": "list123"}, mock_context)
        url = mock_context.fetch.call_args.args[0]
        assert "list123" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        result = await mailchimp.execute_action("get_list", {"list_id": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE LIST
# =============================================================================


SAMPLE_CONTACT = {
    "company": "Acme",
    "address1": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip": "62701",
    "country": "US",
}
SAMPLE_CAMPAIGN_DEFAULTS = {
    "from_name": "Acme Newsletter",
    "from_email": "news@acme.com",
    "subject": "Our Newsletter",
    "language": "en",
}


class TestCreateList:
    @pytest.mark.asyncio
    async def test_creates_list_successfully(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "new123", "name": "My New List"})
        result = await mailchimp.execute_action(
            "create_list",
            {
                "name": "My New List",
                "permission_reminder": "You signed up on our site.",
                "contact": SAMPLE_CONTACT,
                "campaign_defaults": SAMPLE_CAMPAIGN_DEFAULTS,
            },
            mock_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["list"]["id"] == "new123"
        assert data["list"]["name"] == "My New List"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "x", "name": "x"})
        await mailchimp.execute_action(
            "create_list",
            {
                "name": "Test",
                "permission_reminder": "r",
                "contact": SAMPLE_CONTACT,
                "campaign_defaults": SAMPLE_CAMPAIGN_DEFAULTS,
            },
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_includes_all_required_fields(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "x", "name": "Test"})
        await mailchimp.execute_action(
            "create_list",
            {
                "name": "Test",
                "permission_reminder": "Signed up via form",
                "contact": SAMPLE_CONTACT,
                "campaign_defaults": SAMPLE_CAMPAIGN_DEFAULTS,
            },
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["name"] == "Test"
        assert payload["permission_reminder"] == "Signed up via form"
        assert payload["contact"] == SAMPLE_CONTACT
        assert payload["campaign_defaults"] == SAMPLE_CAMPAIGN_DEFAULTS

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await mailchimp.execute_action(
            "create_list",
            {
                "name": "Test",
                "permission_reminder": "r",
                "contact": SAMPLE_CONTACT,
                "campaign_defaults": SAMPLE_CAMPAIGN_DEFAULTS,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# ADD MEMBER
# =============================================================================


class TestAddMember:
    @pytest.mark.asyncio
    async def test_adds_member_successfully(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"id": "mem123", "email_address": "user@example.com", "status": "subscribed"}
        )
        result = await mailchimp.execute_action(
            "add_member",
            {"list_id": "list1", "email_address": "user@example.com", "status": "subscribed"},
            mock_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["member"]["email_address"] == "user@example.com"
        assert data["member"]["status"] == "subscribed"

    @pytest.mark.asyncio
    async def test_request_url_contains_list_id(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "a@b.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "add_member",
            {"list_id": "list99", "email_address": "a@b.com", "status": "subscribed"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "list99/members" in url

    @pytest.mark.asyncio
    async def test_optional_merge_fields_included(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "a@b.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "add_member",
            {
                "list_id": "list1",
                "email_address": "a@b.com",
                "status": "subscribed",
                "merge_fields": {"FNAME": "John", "LNAME": "Doe"},
            },
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["merge_fields"] == {"FNAME": "John", "LNAME": "Doe"}

    @pytest.mark.asyncio
    async def test_optional_tags_included(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "a@b.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "add_member",
            {"list_id": "list1", "email_address": "a@b.com", "status": "subscribed", "tags": ["vip", "new"]},
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["tags"] == ["vip", "new"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Duplicate email")
        result = await mailchimp.execute_action(
            "add_member",
            {"list_id": "l1", "email_address": "x@x.com", "status": "subscribed"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# UPDATE MEMBER
# =============================================================================


class TestUpdateMember:
    @pytest.mark.asyncio
    async def test_updates_member_by_email(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"id": "m1", "email_address": "user@example.com", "status": "unsubscribed"}
        )
        result = await mailchimp.execute_action(
            "update_member",
            {"list_id": "list1", "email_address": "user@example.com", "status": "unsubscribed"},
            mock_context,
        )
        assert result.result.data["result"] is True
        assert result.result.data["member"]["status"] == "unsubscribed"

    @pytest.mark.asyncio
    async def test_uses_subscriber_hash_in_url(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "user@example.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "update_member",
            {"list_id": "list1", "email_address": "user@example.com"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        # MD5 of "user@example.com" is b58996c504c5638798eb6b511e6f49af
        assert "b58996c504c5638798eb6b511e6f49af" in url

    @pytest.mark.asyncio
    async def test_accepts_direct_subscriber_hash(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "x@x.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "update_member",
            {"list_id": "list1", "subscriber_hash": "abc123hash"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "abc123hash" in url

    @pytest.mark.asyncio
    async def test_uses_patch_method(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "x@x.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "update_member",
            {"list_id": "list1", "email_address": "x@x.com", "status": "pending"},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_missing_both_hash_and_email_returns_error(self, mock_context):
        result = await mailchimp.execute_action("update_member", {"list_id": "list1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "subscriber_hash or email_address" in result.result.message

    @pytest.mark.asyncio
    async def test_optional_fields_included_in_payload(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "x@x.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "update_member",
            {
                "list_id": "list1",
                "email_address": "x@x.com",
                "merge_fields": {"FNAME": "Jane"},
                "tags": ["vip"],
            },
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["merge_fields"] == {"FNAME": "Jane"}
        assert payload["tags"] == ["vip"]

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "x@x.com", "status": "pending"})
        result = await mailchimp.execute_action(
            "update_member",
            {"list_id": "list1", "email_address": "x@x.com"},
            mock_context,
        )
        member = result.result.data["member"]
        assert "id" in member
        assert "email_address" in member
        assert "status" in member


# =============================================================================
# GET MEMBER
# =============================================================================


class TestGetMember:
    @pytest.mark.asyncio
    async def test_returns_member_details(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "id": "m1",
                "email_address": "user@example.com",
                "status": "subscribed",
                "merge_fields": {"FNAME": "John"},
            }
        )
        result = await mailchimp.execute_action(
            "get_member",
            {"list_id": "list1", "email_address": "user@example.com"},
            mock_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["member"]["email_address"] == "user@example.com"
        assert data["member"]["merge_fields"] == {"FNAME": "John"}

    @pytest.mark.asyncio
    async def test_generates_hash_from_email(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "user@example.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "get_member",
            {"list_id": "list1", "email_address": "user@example.com"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "b58996c504c5638798eb6b511e6f49af" in url

    @pytest.mark.asyncio
    async def test_missing_hash_and_email_returns_error(self, mock_context):
        result = await mailchimp.execute_action("get_member", {"list_id": "list1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "subscriber_hash or email_address" in result.result.message

    @pytest.mark.asyncio
    async def test_accepts_direct_subscriber_hash(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "m1", "email_address": "x@x.com", "status": "subscribed"})
        await mailchimp.execute_action(
            "get_member",
            {"list_id": "list1", "subscriber_hash": "directhash999"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "directhash999" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Member not found")
        result = await mailchimp.execute_action(
            "get_member",
            {"list_id": "list1", "email_address": "gone@example.com"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET LIST MEMBERS
# =============================================================================


class TestGetListMembers:
    @pytest.mark.asyncio
    async def test_returns_members(self, mock_context):
        members = [
            {"id": "m1", "email_address": "a@b.com", "status": "subscribed"},
            {"id": "m2", "email_address": "c@d.com", "status": "pending"},
        ]
        mock_context.fetch.return_value = ok({"members": members, "total_items": 2})
        result = await mailchimp.execute_action("get_list_members", {"list_id": "list1"}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert len(data["members"]) == 2
        assert data["total_items"] == 2

    @pytest.mark.asyncio
    async def test_url_contains_list_id(self, mock_context):
        mock_context.fetch.return_value = ok({"members": [], "total_items": 0})
        await mailchimp.execute_action("get_list_members", {"list_id": "mylist"}, mock_context)
        url = mock_context.fetch.call_args.args[0]
        assert "mylist/members" in url

    @pytest.mark.asyncio
    async def test_status_filter_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"members": [], "total_items": 0})
        await mailchimp.execute_action(
            "get_list_members",
            {"list_id": "list1", "status": "subscribed"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["status"] == "subscribed"

    @pytest.mark.asyncio
    async def test_no_status_filter_when_not_provided(self, mock_context):
        mock_context.fetch.return_value = ok({"members": [], "total_items": 0})
        await mailchimp.execute_action("get_list_members", {"list_id": "list1"}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert "status" not in params

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("List not found")
        result = await mailchimp.execute_action("get_list_members", {"list_id": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# FIND CAMPAIGN
# =============================================================================


SAMPLE_CAMPAIGN = {
    "id": "cmp1",
    "type": "regular",
    "status": "save",
    "settings": {"title": "Summer Sale", "subject_line": "Big deals inside"},
}


class TestFindCampaign:
    @pytest.mark.asyncio
    async def test_finds_by_title(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [SAMPLE_CAMPAIGN]})
        result = await mailchimp.execute_action("find_campaign", {"query": "summer"}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["campaign"]["id"] == "cmp1"

    @pytest.mark.asyncio
    async def test_finds_by_subject_line(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [SAMPLE_CAMPAIGN]})
        result = await mailchimp.execute_action("find_campaign", {"query": "big deals"}, mock_context)
        assert result.result.data["campaign"]["id"] == "cmp1"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [SAMPLE_CAMPAIGN]})
        result = await mailchimp.execute_action("find_campaign", {"query": "nonexistent query xyz"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await mailchimp.execute_action("find_campaign", {"query": "test"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_fetches_with_count_100(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": []})
        await mailchimp.execute_action("find_campaign", {"query": "x"}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == 100


# =============================================================================
# GET CAMPAIGNS
# =============================================================================


class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_returns_campaigns(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [SAMPLE_CAMPAIGN], "total_items": 1})
        result = await mailchimp.execute_action("get_campaigns", {}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert len(data["campaigns"]) == 1
        assert data["total_items"] == 1

    @pytest.mark.asyncio
    async def test_status_filter_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [], "total_items": 0})
        await mailchimp.execute_action("get_campaigns", {"status": "sent"}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["status"] == "sent"

    @pytest.mark.asyncio
    async def test_default_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"campaigns": [], "total_items": 0})
        await mailchimp.execute_action("get_campaigns", {}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == 10
        assert params["offset"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Service unavailable")
        result = await mailchimp.execute_action("get_campaigns", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE CAMPAIGN
# =============================================================================


class TestCreateCampaign:
    @pytest.mark.asyncio
    async def test_creates_campaign_successfully(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "cmp_new", "type": "regular", "status": "save"})
        result = await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": "list1",
                "subject_line": "Monthly Update",
                "from_name": "Acme",
                "reply_to": "noreply@acme.com",
            },
            mock_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["campaign"]["id"] == "cmp_new"
        assert data["campaign"]["type"] == "regular"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "c1", "type": "regular", "status": "save"})
        await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": "l1",
                "subject_line": "Test",
                "from_name": "Me",
                "reply_to": "me@me.com",
            },
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "c1", "type": "regular", "status": "save"})
        await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": "list1",
                "subject_line": "Hello",
                "from_name": "Sender",
                "reply_to": "reply@example.com",
                "title": "My Campaign",
            },
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["type"] == "regular"
        assert payload["recipients"]["list_id"] == "list1"
        assert payload["settings"]["subject_line"] == "Hello"
        assert payload["settings"]["from_name"] == "Sender"
        assert payload["settings"]["reply_to"] == "reply@example.com"
        assert payload["settings"]["title"] == "My Campaign"

    @pytest.mark.asyncio
    async def test_title_is_optional(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "c1", "type": "regular", "status": "save"})
        await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": "l1",
                "subject_line": "Hi",
                "from_name": "Me",
                "reply_to": "me@me.com",
            },
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "title" not in payload["settings"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad request")
        result = await mailchimp.execute_action(
            "create_campaign",
            {
                "type": "regular",
                "list_id": "l1",
                "subject_line": "Hi",
                "from_name": "Me",
                "reply_to": "me@me.com",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET CAMPAIGN
# =============================================================================


class TestGetCampaign:
    @pytest.mark.asyncio
    async def test_returns_campaign_details(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_CAMPAIGN)
        result = await mailchimp.execute_action("get_campaign", {"campaign_id": "cmp1"}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert data["campaign"]["id"] == "cmp1"

    @pytest.mark.asyncio
    async def test_request_url_contains_campaign_id(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_CAMPAIGN)
        await mailchimp.execute_action("get_campaign", {"campaign_id": "cmp99"}, mock_context)
        url = mock_context.fetch.call_args.args[0]
        assert "cmp99" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Campaign not found")
        result = await mailchimp.execute_action("get_campaign", {"campaign_id": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Campaign not found" in result.result.message
