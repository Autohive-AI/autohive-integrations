from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult,
    ConnectedAccountHandler, ConnectedAccountInfo
)
from typing import Dict, Any, List, Optional
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
        super().__init__(
            f"Mailchimp API rate limit exceeded. Retry after {retry_after} seconds."
        )


class MailchimpRateLimiter:
    def __init__(self, default_retry_delay: int = 60, max_retries: int = 3):
        """
        Handles Mailchimp API rate limiting by retrying requests on 429 errors.
        Mailchimp has a limit of 10 simultaneous connections.
        """
        self.default_retry_delay = default_retry_delay
        self.max_retries = max_retries

    def _extract_retry_delay(self, error_response) -> int:
        """Extract retry delay from error response headers"""
        if hasattr(error_response, 'headers'):
            retry_after = error_response.headers.get('Retry-After')
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
                return response

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a rate limit error (HTTP 429)
                if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
                    # Don't retry on the last attempt
                    if attempt >= self.max_retries:
                        delay = self._extract_retry_delay(e)
                        raise MailchimpRateLimitException(delay)

                    # Get delay from response headers or use default
                    delay = self._extract_retry_delay(e)

                    # Wait and retry
                    await asyncio.sleep(delay)
                    continue

                # For non-rate-limit errors, fail immediately
                raise e

        # All retries exhausted, raise the last error if present, else raise generic exception
        if last_error is not None:
            raise last_error
        else:
            raise Exception("All retries exhausted, but no exception was captured.")


# Global rate limiter instance
rate_limiter = MailchimpRateLimiter()


# ---- Helper Functions ----

def get_mailchimp_base_url(dc: str) -> str:
    """
    Build Mailchimp API base URL using data center from metadata.
    The dc (data center) must be fetched from the OAuth2 metadata endpoint.
    """
    return f"https://{dc}.api.mailchimp.com/3.0"


def get_data_center(context: ExecutionContext) -> str:
    """
    Get the data center (dc) for Mailchimp API requests from stored connection metadata.

    The dc is stored in metadata during the OAuth flow by the backend.

    Returns the dc string (e.g., 'us19')
    """
    if hasattr(context, 'metadata') and context.metadata:
        dc = context.metadata.get("dc")
        if dc:
            return dc

    raise ValueError("Mailchimp data center (dc) not found in connection metadata")


def get_subscriber_hash(email: str) -> str:
    """
    Generate MD5 hash of lowercase email address.
    Required for Mailchimp member operations.
    """
    return hashlib.md5(email.lower().encode()).hexdigest()


# ---- Action Handlers ----


@mailchimp.action("get_lists")
class GetListsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Retrieve all mailing lists from Mailchimp account
        """
        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL with pagination parameters
            url = f"{base_url}/lists"
            params = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0)
            }

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "result": True,
                    "lists": response.get("lists", []),
                    "total_items": response.get("total_items", 0)
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
                    "lists": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e),
                    "lists": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )


@mailchimp.action("find_list")
class FindListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Search for a mailing list by name
        """
        # Validate required inputs
        name = inputs.get("name")
        if not name:
            return ActionResult(
                data={
                    "result": False,
                    "error": "name is required"
                },
                cost_usd=0.0
            )

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL - fetch lists and filter by name
            url = f"{base_url}/lists"
            params = {
                "count": 100,  # Fetch enough to find the match
                "offset": 0
            }

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET",
                params=params
            )

            # Search for matching list (case-insensitive)
            search_name = name.lower()
            matching_list = None
            for lst in response.get("lists", []):
                if search_name in lst.get("name", "").lower():
                    matching_list = lst
                    break

            if matching_list:
                return ActionResult(
                    data={
                        "result": True,
                        "list": matching_list
                    },
                    cost_usd=0.0
                )
            else:
                return ActionResult(
                    data={
                        "result": False,
                        "error": f"No list found matching '{name}'"
                    },
                    cost_usd=0.0
                )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("get_list")
class GetListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Get details of a specific mailing list
        """
        # Validate required inputs
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionResult(
                data={
                    "result": False,
                    "error": "list_id is required"
                },
                cost_usd=0.0
            )

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL
            url = f"{base_url}/lists/{list_id}"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET"
            )

            return ActionResult(
                data={
                    "result": True,
                    "list": response
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("create_list")
class CreateListAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Create a new mailing list in Mailchimp
        """
        # Validate required inputs
        name = inputs.get("name")
        permission_reminder = inputs.get("permission_reminder")
        contact = inputs.get("contact")
        campaign_defaults = inputs.get("campaign_defaults")

        if not name:
            return ActionResult(data={"result": False, "error": "name is required"}, cost_usd=0.0)
        if not permission_reminder:
            return ActionResult(data={"result": False, "error": "permission_reminder is required"}, cost_usd=0.0)
        if not contact:
            return ActionResult(data={"result": False, "error": "contact is required"}, cost_usd=0.0)
        if not campaign_defaults:
            return ActionResult(data={"result": False, "error": "campaign_defaults is required"}, cost_usd=0.0)

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build list payload
            list_data = {
                "name": name,
                "permission_reminder": permission_reminder,
                "contact": contact,
                "campaign_defaults": campaign_defaults,
                "email_type_option": inputs.get("email_type_option", True)
            }

            # Build URL
            url = f"{base_url}/lists"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="POST",
                json=list_data
            )

            return ActionResult(
                data={
                    "result": True,
                    "list": {
                        "id": response.get("id"),
                        "name": response.get("name")
                    }
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("add_member")
class AddMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Add a new member to a mailing list
        """
        # Validate required inputs
        list_id = inputs.get("list_id")
        email_address = inputs.get("email_address")
        status = inputs.get("status")

        if not list_id:
            return ActionResult(data={"result": False, "error": "list_id is required"}, cost_usd=0.0)
        if not email_address:
            return ActionResult(data={"result": False, "error": "email_address is required"}, cost_usd=0.0)
        if not status:
            return ActionResult(data={"result": False, "error": "status is required"}, cost_usd=0.0)

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build member payload
            member_data = {
                "email_address": email_address,
                "status": status
            }

            # Add optional fields
            if inputs.get("merge_fields"):
                member_data["merge_fields"] = inputs["merge_fields"]

            if inputs.get("tags"):
                member_data["tags"] = inputs["tags"]

            # Build URL
            url = f"{base_url}/lists/{list_id}/members"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="POST",
                json=member_data
            )

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": response.get("id"),
                        "email_address": response.get("email_address"),
                        "status": response.get("status")
                    }
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("update_member")
class UpdateMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Update an existing member in a mailing list
        """
        # Validate required inputs
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionResult(data={"result": False, "error": "list_id is required"}, cost_usd=0.0)

        # Get subscriber hash from either direct hash or email
        subscriber_hash = inputs.get("subscriber_hash")
        email_address = inputs.get("email_address")

        if not subscriber_hash and not email_address:
            return ActionResult(
                data={
                    "result": False,
                    "error": "Either subscriber_hash or email_address is required"
                },
                cost_usd=0.0
            )

        if not subscriber_hash and email_address:
            subscriber_hash = get_subscriber_hash(email_address)

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build member update payload
            member_data = {}

            # Add optional fields only if provided
            if email_address:
                member_data["email_address"] = email_address
            if inputs.get("status"):
                member_data["status"] = inputs["status"]
            if inputs.get("merge_fields"):
                member_data["merge_fields"] = inputs["merge_fields"]
            if inputs.get("tags"):
                member_data["tags"] = inputs["tags"]

            # Build URL
            url = f"{base_url}/lists/{list_id}/members/{subscriber_hash}"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="PATCH",
                json=member_data
            )

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": response.get("id"),
                        "email_address": response.get("email_address"),
                        "status": response.get("status")
                    }
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("get_member")
class GetMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Get details of a specific member in a mailing list
        """
        # Validate required inputs
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionResult(data={"result": False, "error": "list_id is required"}, cost_usd=0.0)

        # Get subscriber hash from either direct hash or email
        subscriber_hash = inputs.get("subscriber_hash")
        email_address = inputs.get("email_address")

        if not subscriber_hash and not email_address:
            return ActionResult(
                data={
                    "result": False,
                    "error": "Either subscriber_hash or email_address is required"
                },
                cost_usd=0.0
            )

        if not subscriber_hash and email_address:
            subscriber_hash = get_subscriber_hash(email_address)

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL
            url = f"{base_url}/lists/{list_id}/members/{subscriber_hash}"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET"
            )

            return ActionResult(
                data={
                    "result": True,
                    "member": {
                        "id": response.get("id"),
                        "email_address": response.get("email_address"),
                        "status": response.get("status"),
                        "merge_fields": response.get("merge_fields", {})
                    }
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("get_list_members")
class GetListMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Get all members from a mailing list
        """
        # Validate required inputs
        list_id = inputs.get("list_id")
        if not list_id:
            return ActionResult(
                data={
                    "result": False,
                    "error": "list_id is required",
                    "members": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL with pagination and filter parameters
            url = f"{base_url}/lists/{list_id}/members"
            params = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0)
            }

            # Add optional status filter
            if inputs.get("status"):
                params["status"] = inputs["status"]

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "result": True,
                    "members": response.get("members", []),
                    "total_items": response.get("total_items", 0)
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
                    "members": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e),
                    "members": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )


@mailchimp.action("find_campaign")
class FindCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Search for a campaign by title or subject line
        """
        # Validate required inputs
        query = inputs.get("query")
        if not query:
            return ActionResult(
                data={
                    "result": False,
                    "error": "query is required"
                },
                cost_usd=0.0
            )

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL - fetch campaigns and filter by title/subject
            url = f"{base_url}/campaigns"
            params = {
                "count": 100,  # Fetch enough to find the match
                "offset": 0
            }

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET",
                params=params
            )

            # Search for matching campaign (case-insensitive in title or subject_line)
            search_query = query.lower()
            matching_campaign = None
            for campaign in response.get("campaigns", []):
                settings = campaign.get("settings", {})
                title = settings.get("title", "").lower()
                subject_line = settings.get("subject_line", "").lower()
                if search_query in title or search_query in subject_line:
                    matching_campaign = campaign
                    break

            if matching_campaign:
                return ActionResult(
                    data={
                        "result": True,
                        "campaign": matching_campaign
                    },
                    cost_usd=0.0
                )
            else:
                return ActionResult(
                    data={
                        "result": False,
                        "error": f"No campaign found matching '{query}'"
                    },
                    cost_usd=0.0
                )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("get_campaigns")
class GetCampaignsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Retrieve all campaigns from Mailchimp account
        """
        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL with pagination and filter parameters
            url = f"{base_url}/campaigns"
            params = {
                "count": inputs.get("count", 10),
                "offset": inputs.get("offset", 0)
            }

            # Add optional status filter
            if inputs.get("status"):
                params["status"] = inputs["status"]

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "result": True,
                    "campaigns": response.get("campaigns", []),
                    "total_items": response.get("total_items", 0)
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
                    "campaigns": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e),
                    "campaigns": [],
                    "total_items": 0
                },
                cost_usd=0.0
            )


@mailchimp.action("create_campaign")
class CreateCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Create a new email campaign in Mailchimp
        """
        # Validate required inputs
        campaign_type = inputs.get("type")
        list_id = inputs.get("list_id")
        subject_line = inputs.get("subject_line")
        from_name = inputs.get("from_name")
        reply_to = inputs.get("reply_to")

        if not campaign_type:
            return ActionResult(data={"result": False, "error": "type is required"}, cost_usd=0.0)
        if not list_id:
            return ActionResult(data={"result": False, "error": "list_id is required"}, cost_usd=0.0)
        if not subject_line:
            return ActionResult(data={"result": False, "error": "subject_line is required"}, cost_usd=0.0)
        if not from_name:
            return ActionResult(data={"result": False, "error": "from_name is required"}, cost_usd=0.0)
        if not reply_to:
            return ActionResult(data={"result": False, "error": "reply_to is required"}, cost_usd=0.0)

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build campaign payload
            campaign_data = {
                "type": campaign_type,
                "recipients": {
                    "list_id": list_id
                },
                "settings": {
                    "subject_line": subject_line,
                    "from_name": from_name,
                    "reply_to": reply_to
                }
            }

            # Add optional title
            if inputs.get("title"):
                campaign_data["settings"]["title"] = inputs["title"]

            # Build URL
            url = f"{base_url}/campaigns"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="POST",
                json=campaign_data
            )

            return ActionResult(
                data={
                    "result": True,
                    "campaign": {
                        "id": response.get("id"),
                        "type": response.get("type"),
                        "status": response.get("status")
                    }
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@mailchimp.action("get_campaign")
class GetCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Get details of a specific campaign
        """
        # Validate required inputs
        campaign_id = inputs.get("campaign_id")
        if not campaign_id:
            return ActionResult(
                data={
                    "result": False,
                    "error": "campaign_id is required"
                },
                cost_usd=0.0
            )

        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Build URL
            url = f"{base_url}/campaigns/{campaign_id}"

            # Make rate-limited request
            response = await rate_limiter.make_request(
                context,
                url,
                method="GET"
            )

            return ActionResult(
                data={
                    "result": True,
                    "campaign": response
                },
                cost_usd=0.0
            )

        except MailchimpRateLimitException as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds."
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

# ---- Connected Account Handler ----


@mailchimp.connected_account()
class MailchimpConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch Mailchimp account information to display which account is connected.
        This is automatically called when a user authorizes the integration.
        """
        try:
            # Get data center from metadata
            dc = get_data_center(context)
            base_url = get_mailchimp_base_url(dc)

            # Fetch account information from Mailchimp API
            # The root endpoint returns information about the authenticated account
            url = f"{base_url}/"

            response = await rate_limiter.make_request(
                context,
                url,
                method="GET"
            )

            # Extract relevant account information
            # Mailchimp returns: account_id, account_name, email, role, etc.
            return ConnectedAccountInfo(
                email=response.get("email"),
                username=response.get("username") or response.get("login_name"),
                first_name=response.get("first_name"),
                last_name=response.get("last_name"),
                organization=response.get("account_name"),
                user_id=response.get("account_id")
            )

        except Exception as e:
            # If we can't fetch account info, log and return None
            # The system will handle this gracefully
            raise Exception(f"Failed to fetch Mailchimp account info: {str(e)}")
