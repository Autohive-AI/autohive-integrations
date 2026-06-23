from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
)
from typing import Dict, Any
import asyncio
import hashlib

# Create the integration using the config.json
mailchimp = Integration.load()


# ---- Rate Limiting ----


class MailchimpRateLimitException(Exception):
    """
    Exception raised when Mailchimp API rate limit is exceeded.
    Mailchimp allows max 10 simultaneous connections and returns 429 on rate limit.
    """

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Mailchimp API rate limit exceeded. Retry after {retry_after} seconds.")


class MailchimpRateLimiter:
    def __init__(self, default_retry_delay: int = 60, max_retries: int = 3):
        """
        Handles Mailchimp API rate limiting by retrying requests on 429 errors.
        Mailchimp has a limit of 10 simultaneous connections.
        """
        self.default_retry_delay = default_retry_delay
        self.max_retries = max_retries

    def _extract_retry_delay(self, response) -> int:
        """Extract retry delay from FetchResponse headers"""
        if hasattr(response, "headers"):
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
        return self.default_retry_delay

    async def make_request(self, context: ExecutionContext, url: str, **kwargs) -> Dict[str, Any]:
        """Make request to Mailchimp API with automatic retry on rate limit errors"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await context.fetch(url, **kwargs)

                if response.status == 429:
                    if attempt >= self.max_retries:
                        delay = self._extract_retry_delay(response)
                        raise MailchimpRateLimitException(delay)
                    delay = self._extract_retry_delay(response)
                    await asyncio.sleep(delay)
                    continue

                return response.data

            except MailchimpRateLimitException:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                    if attempt >= self.max_retries:
                        raise MailchimpRateLimitException(self.default_retry_delay)
                    await asyncio.sleep(self.default_retry_delay)
                    continue

                raise e

        if last_error is not None:
            raise last_error
        else:
            raise Exception("All retries exhausted, but no exception was captured.")


# Global rate limiter instance
rate_limiter = MailchimpRateLimiter()


# ---- Helper Functions ----


def get_mailchimp_base_url(dc: str) -> str:
    """Build Mailchimp API base URL using data center from metadata."""
    return f"https://{dc}.api.mailchimp.com/3.0"


def get_data_center(context: ExecutionContext) -> str:
    """
    Get the data center (dc) for Mailchimp API requests from stored connection metadata.
    The dc is stored in metadata during the OAuth flow by the backend.
    """
    if hasattr(context, "metadata") and context.metadata:
        dc = context.metadata.get("dc")
        if dc:
            return dc

    raise ValueError("Mailchimp data center (dc) not found in connection metadata")


def get_subscriber_hash(email: str) -> str:
    """Generate MD5 hash of lowercase email address. Required for Mailchimp member operations."""
    return hashlib.md5(email.lower().encode(), usedforsecurity=False).hexdigest()  # nosec B324


# ---- Action Handlers ----


@mailchimp.action("get_lists")
class GetListsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/lists"
            params = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0),
            }

            body = await rate_limiter.make_request(context, url, method="GET", params=params)

            return ActionResult(
                data={
                    "result": True,
                    "lists": body.get("lists", []),
                    "total_items": body.get("total_items", 0),
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("find_list")
class FindListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        name = inputs.get("name")
        if not name:
            return ActionError(message="name is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/lists"
            params = {"count": 100, "offset": 0}

            body = await rate_limiter.make_request(context, url, method="GET", params=params)

            search_name = name.lower()
            matching_list = None
            for lst in body.get("lists", []):
                if search_name in lst.get("name", "").lower():
                    matching_list = lst
                    break

            if matching_list:
                return ActionResult(data={"result": True, "list": matching_list}, cost_usd=0.0)
            else:
                return ActionError(message=f"No list found matching '{name}'")

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("get_list")
class GetListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionError(message="list_id is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/lists/{list_id}"
            body = await rate_limiter.make_request(context, url, method="GET")

            return ActionResult(data={"result": True, "list": body}, cost_usd=0.0)

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("create_list")
class CreateListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        name = inputs.get("name")
        permission_reminder = inputs.get("permission_reminder")
        contact = inputs.get("contact")
        campaign_defaults = inputs.get("campaign_defaults")

        if not name:
            return ActionError(message="name is required")
        if not permission_reminder:
            return ActionError(message="permission_reminder is required")
        if not contact:
            return ActionError(message="contact is required")
        if not campaign_defaults:
            return ActionError(message="campaign_defaults is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            list_data = {
                "name": name,
                "permission_reminder": permission_reminder,
                "contact": contact,
                "campaign_defaults": campaign_defaults,
                "email_type_option": inputs.get("email_type_option", True),
            }

            url = f"{base_url}/lists"
            body = await rate_limiter.make_request(context, url, method="POST", json=list_data)

            return ActionResult(
                data={
                    "result": True,
                    "list": {"id": body.get("id"), "name": body.get("name")},
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("add_member")
class AddMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs.get("list_id")
        email_address = inputs.get("email_address")
        status = inputs.get("status")

        if not list_id:
            return ActionError(message="list_id is required")
        if not email_address:
            return ActionError(message="email_address is required")
        if not status:
            return ActionError(message="status is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            member_data: Dict[str, Any] = {"email_address": email_address, "status": status}

            if inputs.get("merge_fields"):
                member_data["merge_fields"] = inputs["merge_fields"]
            if inputs.get("tags"):
                member_data["tags"] = inputs["tags"]

            url = f"{base_url}/lists/{list_id}/members"
            body = await rate_limiter.make_request(context, url, method="POST", json=member_data)

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": body.get("id"),
                        "email_address": body.get("email_address"),
                        "status": body.get("status"),
                    },
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("update_member")
class UpdateMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionError(message="list_id is required")

        subscriber_hash = inputs.get("subscriber_hash")
        email_address = inputs.get("email_address")

        if not subscriber_hash and not email_address:
            return ActionError(message="Either subscriber_hash or email_address is required")

        if not subscriber_hash and email_address:
            subscriber_hash = get_subscriber_hash(email_address)

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            member_data: Dict[str, Any] = {}

            if email_address:
                member_data["email_address"] = email_address
            if inputs.get("status"):
                member_data["status"] = inputs["status"]
            if inputs.get("merge_fields"):
                member_data["merge_fields"] = inputs["merge_fields"]
            if inputs.get("tags"):
                member_data["tags"] = inputs["tags"]

            url = f"{base_url}/lists/{list_id}/members/{subscriber_hash}"
            body = await rate_limiter.make_request(context, url, method="PATCH", json=member_data)

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": body.get("id"),
                        "email_address": body.get("email_address"),
                        "status": body.get("status"),
                    },
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("get_member")
class GetMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionError(message="list_id is required")

        subscriber_hash = inputs.get("subscriber_hash")
        email_address = inputs.get("email_address")

        if not subscriber_hash and not email_address:
            return ActionError(message="Either subscriber_hash or email_address is required")

        if not subscriber_hash and email_address:
            subscriber_hash = get_subscriber_hash(email_address)

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/lists/{list_id}/members/{subscriber_hash}"
            body = await rate_limiter.make_request(context, url, method="GET")

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": body.get("id"),
                        "email_address": body.get("email_address"),
                        "status": body.get("status"),
                        "merge_fields": body.get("merge_fields", {}),
                    },
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("get_list_members")
class GetListMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionError(message="list_id is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/lists/{list_id}/members"
            params: Dict[str, Any] = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0),
            }

            if inputs.get("status"):
                params["status"] = inputs["status"]

            body = await rate_limiter.make_request(context, url, method="GET", params=params)

            return ActionResult(
                data={
                    "result": True,
                    "members": body.get("members", []),
                    "total_items": body.get("total_items", 0),
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("find_campaign")
class FindCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = inputs.get("query")
        if not query:
            return ActionError(message="query is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/campaigns"
            params = {"count": 100, "offset": 0}

            body = await rate_limiter.make_request(context, url, method="GET", params=params)

            search_query = query.lower()
            matching_campaign = None
            for campaign in body.get("campaigns", []):
                settings = campaign.get("settings", {})
                title = settings.get("title", "").lower()
                subject_line = settings.get("subject_line", "").lower()
                if search_query in title or search_query in subject_line:
                    matching_campaign = campaign
                    break

            if matching_campaign:
                return ActionResult(data={"result": True, "campaign": matching_campaign}, cost_usd=0.0)
            else:
                return ActionError(message=f"No campaign found matching '{query}'")

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("get_campaigns")
class GetCampaignsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/campaigns"
            params: Dict[str, Any] = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0),
            }

            if inputs.get("status"):
                params["status"] = inputs["status"]

            body = await rate_limiter.make_request(context, url, method="GET", params=params)

            return ActionResult(
                data={
                    "result": True,
                    "campaigns": body.get("campaigns", []),
                    "total_items": body.get("total_items", 0),
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("create_campaign")
class CreateCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        campaign_type = inputs.get("type")
        list_id = inputs.get("list_id")
        subject_line = inputs.get("subject_line")
        from_name = inputs.get("from_name")
        reply_to = inputs.get("reply_to")

        if not campaign_type:
            return ActionError(message="type is required")
        if not list_id:
            return ActionError(message="list_id is required")
        if not subject_line:
            return ActionError(message="subject_line is required")
        if not from_name:
            return ActionError(message="from_name is required")
        if not reply_to:
            return ActionError(message="reply_to is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            campaign_data: Dict[str, Any] = {
                "type": campaign_type,
                "recipients": {"list_id": list_id},
                "settings": {
                    "subject_line": subject_line,
                    "from_name": from_name,
                    "reply_to": reply_to,
                },
            }

            if inputs.get("title"):
                campaign_data["settings"]["title"] = inputs["title"]

            url = f"{base_url}/campaigns"
            body = await rate_limiter.make_request(context, url, method="POST", json=campaign_data)

            return ActionResult(
                data={
                    "result": True,
                    "campaign": {
                        "id": body.get("id"),
                        "type": body.get("type"),
                        "status": body.get("status"),
                    },
                },
                cost_usd=0.0,
            )

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


@mailchimp.action("get_campaign")
class GetCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        campaign_id = inputs.get("campaign_id")
        if not campaign_id:
            return ActionError(message="campaign_id is required")

        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/campaigns/{campaign_id}"
            body = await rate_limiter.make_request(context, url, method="GET")

            return ActionResult(data={"result": True, "campaign": body}, cost_usd=0.0)

        except MailchimpRateLimitException as e:
            return ActionError(message=f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception as e:
            return ActionError(message=str(e))


# ---- Connected Account Handler ----


@mailchimp.connected_account()
class MailchimpConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        try:
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            url = f"{base_url}/"
            body = await rate_limiter.make_request(context, url, method="GET")

            return ConnectedAccountInfo(
                email=body.get("email"),
                username=body.get("username") or body.get("login_name"),
                first_name=body.get("first_name"),
                last_name=body.get("last_name"),
                organization=body.get("account_name"),
                user_id=body.get("account_id"),
            )

        except Exception as e:
            raise Exception(f"Failed to fetch Mailchimp account info: {str(e)}")
