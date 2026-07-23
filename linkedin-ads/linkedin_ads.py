import urllib.parse

import yarl

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, Optional
from datetime import datetime, timezone

linkedin_ads = Integration.load()

# LinkedIn Marketing API Configuration
API_BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202601"

# Analytics fields that exist in the AdAnalytics v8 schema. Derived metrics
# like costPerClick / clickThroughRate are NOT stored fields and are rejected
# by the API, so they are computed by consumers instead of requested here.
ANALYTICS_FIELDS = "impressions,clicks,costInLocalCurrency,externalWebsiteConversions"


def get_headers() -> Dict[str, str]:
    """Build headers for LinkedIn Marketing API requests."""
    return {
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def build_query(params: Dict[str, Any]) -> str:
    """Build a Rest.li query string.

    LinkedIn's versioned API relies on the structural characters ``( ) , :``
    in finder/analytics syntax (e.g. ``accounts=List(urn:li:sponsoredAccount:1)``
    and ``dateRange=(start:(year:2026,...))``). Those must reach the server
    literally, so they are kept out of percent-encoding. Everything else in a
    value is percent-encoded normally. ``None`` values are skipped.

    This query string is appended to the URL directly rather than passed via
    the SDK's ``params`` argument, because the SDK percent-encodes every value
    (including the structural characters), which the API rejects.

    ``%`` is kept literal too, so URNs whose colons have already been encoded
    with :func:`urn_param` (required inside ``List(...)`` finder values) survive
    intact rather than being double-encoded.
    """
    parts = []
    for key, value in params.items():
        if value is None:
            continue
        parts.append(f"{key}={urllib.parse.quote(str(value), safe='(),:%')}")
    return "&".join(parts)


def urn_param(urn: str) -> str:
    """Percent-encode a URN for embedding inside a Rest.li finder value.

    Inside ``List(...)`` finder values the colons of a URN token must be
    percent-encoded (``urn:li:sponsoredAccount:1`` -> ``urn%3Ali%3A...``) or the
    API rejects the request with ``ILLEGAL_ARGUMENT``. The surrounding
    structural characters stay literal.
    """
    return urllib.parse.quote(urn, safe="")


def extract_id_from_urn(urn: str) -> str:
    """Extract numeric ID from LinkedIn URN with validation."""
    if not urn:
        return urn

    id_part = urn
    if ":" in urn:
        id_part = urn.split(":")[-1]

    if not id_part.isdigit():
        raise ValueError(f"Invalid ID format: {id_part}. Expected numeric ID.")

    return id_part


def build_urn(entity_type: str, entity_id: str) -> str:
    """Build LinkedIn URN from entity type and ID."""
    urn_map = {
        "account": "urn:li:sponsoredAccount",
        "campaign": "urn:li:sponsoredCampaign",
        "campaign_group": "urn:li:sponsoredCampaignGroup",
        "creative": "urn:li:sponsoredCreative",
    }
    prefix = urn_map.get(entity_type, f"urn:li:{entity_type}")
    if entity_id.startswith("urn:"):
        return entity_id
    return f"{prefix}:{entity_id}"


async def li_request(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Call the LinkedIn Marketing API and return the raw response object.

    Non-2xx responses raise (``context.fetch`` raises ``HTTPError``); callers
    convert exceptions into ``ActionError``.

    The query string is baked into the URL and sent as a pre-encoded
    ``yarl.URL`` so aiohttp forwards it verbatim: with the default
    (``encoded=False``) aiohttp decodes the ``%3A`` in URN tokens back to
    literal colons, which LinkedIn's Rest.li parser rejects inside
    ``List(...)`` finder values.
    """
    headers = get_headers()
    if extra_headers:
        headers.update(extra_headers)

    url = f"{API_BASE_URL}{endpoint}"
    if params:
        url = f"{url}?{build_query(params)}"
    request_url = yarl.URL(url, encoded=True)

    if method == "GET":
        return await context.fetch(request_url, headers=headers)
    elif method == "POST":
        return await context.fetch(request_url, method="POST", json=json_body, headers=headers)
    raise ValueError(f"Unsupported HTTP method: {method}")


async def li_fetch(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Call the LinkedIn Marketing API and return the parsed response body."""
    response = await li_request(context, method, endpoint, params, json_body, extra_headers)
    return getattr(response, "data", response)


def created_entity_id(response: Any) -> str:
    """Extract the id of a newly created entity from a create response.

    LinkedIn returns the new id in the JSON body for some resources but in the
    ``x-restli-id`` response header for others (campaigns included). Prefer the
    body, fall back to the header (matched case-insensitively).
    """
    data = getattr(response, "data", None)
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    headers = getattr(response, "headers", None) or {}
    for key, value in headers.items():
        if key.lower() == "x-restli-id":
            return str(value)
    return ""


@linkedin_ads.action("get_ad_accounts")
class GetAdAccountsAction(ActionHandler):
    """Retrieve all ad accounts the authenticated user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page_size = inputs.get("page_size", 25)

            data = await li_fetch(
                context,
                "GET",
                "/adAccountUsers",
                params={"q": "authenticatedUser", "count": page_size},
            )

            elements = (data or {}).get("elements", [])

            account_ids = []
            for element in elements:
                account_urn = element.get("account")
                if account_urn:
                    try:
                        account_ids.append(extract_id_from_urn(account_urn))
                    except ValueError:
                        continue

            # The versioned API does not support BATCH_GET on /adAccounts
            # (ids=List(...) returns 404 RESOURCE_NOT_FOUND), so fetch each
            # account individually via GET /adAccounts/{id}.
            accounts = []
            for account_id in account_ids:
                try:
                    account = await li_fetch(context, "GET", f"/adAccounts/{account_id}")
                except Exception:  # nosec B112 - skip an account that can't be fetched rather than failing the whole listing
                    continue
                if account:
                    accounts.append(account)

            return ActionResult(data={"accounts": accounts}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_campaigns")
class GetCampaignsAction(ActionHandler):
    """Retrieve campaigns for a specific ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            validated_id = extract_id_from_urn(account_id)
            status = inputs.get("status")
            page_size = inputs.get("page_size", 25)
            page_token = inputs.get("page_token")

            # Search finders use cursor-based pagination (pageSize/pageToken)
            # from API version 202401; the old index-based `count` is ignored.
            params = {"q": "search", "pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            if status:
                params["search"] = f"(status:(values:List({status})))"

            # Campaign endpoints are now account-scoped: the account id lives in
            # the URL path, not the query.
            data = await li_fetch(context, "GET", f"/adAccounts/{validated_id}/adCampaigns", params=params)

            campaigns = (data or {}).get("elements", [])
            next_page_token = ((data or {}).get("metadata") or {}).get("nextPageToken")
            return ActionResult(
                data={"campaigns": campaigns, "next_page_token": next_page_token},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_campaign")
class GetCampaignAction(ActionHandler):
    """Retrieve detailed information about a specific campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            campaign_id = inputs["campaign_id"]
            account_id = inputs["account_id"]

            account_numeric_id = extract_id_from_urn(account_id)
            numeric_id = extract_id_from_urn(campaign_id)

            # Campaign endpoints are now account-scoped.
            data = await li_fetch(context, "GET", f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}")

            return ActionResult(data={"campaign": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("create_campaign")
class CreateCampaignAction(ActionHandler):
    """Create a new advertising campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            campaign_group_id = inputs["campaign_group_id"]
            name = inputs["name"]
            objective_type = inputs["objective_type"]
            campaign_type = inputs["type"]
            daily_budget = inputs["daily_budget_amount"]
            currency_code = inputs.get("currency_code", "USD")
            status = inputs.get("status", "DRAFT")
            cost_type = inputs.get("cost_type")
            unit_cost_amount = inputs.get("unit_cost_amount")
            # Required by the API but with sensible defaults so simple creates work.
            locale_country = inputs.get("locale_country", "US")
            locale_language = inputs.get("locale_language", "en")
            offsite_delivery_enabled = inputs.get("offsite_delivery_enabled", False)
            political_intent = inputs.get("political_intent", "NOT_DECLARED")

            account_numeric_id = extract_id_from_urn(account_id)
            account_urn = build_urn("account", account_numeric_id)
            campaign_group_urn = build_urn("campaign_group", extract_id_from_urn(campaign_group_id))

            # runSchedule.start is required; default to now, allow YYYY-MM-DD overrides.
            start_date = inputs.get("start_date")
            end_date = inputs.get("end_date")
            if start_date:
                start_ms = int(
                    datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
                )
            else:
                start_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            run_schedule = {"start": start_ms}
            if end_date:
                run_schedule["end"] = int(
                    datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
                )

            campaign_data = {
                "account": account_urn,
                "campaignGroup": campaign_group_urn,
                "name": name,
                "objectiveType": objective_type,
                "type": campaign_type,
                "status": status,
                "dailyBudget": {
                    "amount": str(daily_budget),
                    "currencyCode": currency_code,
                },
                "locale": {"country": locale_country, "language": locale_language},
                "offsiteDeliveryEnabled": offsite_delivery_enabled,
                "politicalIntent": political_intent,
                "runSchedule": run_schedule,
            }

            if cost_type:
                campaign_data["costType"] = cost_type
            if unit_cost_amount is not None:
                campaign_data["unitCost"] = {
                    "amount": str(unit_cost_amount),
                    "currencyCode": currency_code,
                }

            # Campaign endpoints are now account-scoped. LinkedIn returns the
            # new campaign id in the x-restli-id response header (not the body),
            # so read the full response rather than just the parsed body.
            response = await li_request(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns",
                json_body=campaign_data,
            )

            # LinkedIn returns the new id in the x-restli-id header with no
            # response body, so only the declared campaign_id is returned.
            campaign_id = created_entity_id(response)
            return ActionResult(data={"campaign_id": campaign_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("update_campaign")
class UpdateCampaignAction(ActionHandler):
    """Update an existing campaign's settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            campaign_id = inputs["campaign_id"]
            account_id = inputs["account_id"]

            account_numeric_id = extract_id_from_urn(account_id)
            numeric_id = extract_id_from_urn(campaign_id)

            patch_set: Dict[str, Any] = {}
            if inputs.get("name"):
                patch_set["name"] = inputs["name"]
            if inputs.get("status"):
                patch_set["status"] = inputs["status"]
            if inputs.get("daily_budget_amount"):
                patch_set["dailyBudget"] = {
                    "amount": str(inputs["daily_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD"),
                }
            if inputs.get("total_budget_amount"):
                patch_set["totalBudget"] = {
                    "amount": str(inputs["total_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD"),
                }

            if not patch_set:
                return ActionError(message="No update fields provided")

            patch_data = {"patch": {"$set": patch_set}}

            # Campaign endpoints are now account-scoped.
            await li_fetch(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            return ActionResult(data={"message": "Campaign updated successfully"}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("pause_campaign")
class PauseCampaignAction(ActionHandler):
    """Pause an active campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            campaign_id = inputs["campaign_id"]
            account_id = inputs["account_id"]

            account_numeric_id = extract_id_from_urn(account_id)
            numeric_id = extract_id_from_urn(campaign_id)

            patch_data = {"patch": {"$set": {"status": "PAUSED"}}}

            # Campaign endpoints are now account-scoped.
            await li_fetch(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            return ActionResult(data={"message": "Campaign paused successfully"}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("activate_campaign")
class ActivateCampaignAction(ActionHandler):
    """Activate a paused or draft campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            campaign_id = inputs["campaign_id"]
            account_id = inputs["account_id"]

            account_numeric_id = extract_id_from_urn(account_id)
            numeric_id = extract_id_from_urn(campaign_id)

            patch_data = {"patch": {"$set": {"status": "ACTIVE"}}}

            # Campaign endpoints are now account-scoped.
            await li_fetch(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            return ActionResult(data={"message": "Campaign activated successfully"}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_campaign_groups")
class GetCampaignGroupsAction(ActionHandler):
    """Retrieve campaign groups for an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            validated_id = extract_id_from_urn(account_id)
            status = inputs.get("status")
            page_size = inputs.get("page_size", 25)
            page_token = inputs.get("page_token")

            # Search finders use cursor-based pagination (pageSize/pageToken)
            # from API version 202401; the old index-based `count` is ignored.
            params = {"q": "search", "pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            if status:
                params["search"] = f"(status:(values:List({status})))"

            # Campaign group endpoints are now account-scoped.
            data = await li_fetch(context, "GET", f"/adAccounts/{validated_id}/adCampaignGroups", params=params)

            campaign_groups = (data or {}).get("elements", [])
            next_page_token = ((data or {}).get("metadata") or {}).get("nextPageToken")
            return ActionResult(
                data={"campaign_groups": campaign_groups, "next_page_token": next_page_token}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_creatives")
class GetCreativesAction(ActionHandler):
    """Retrieve creatives (ads) for an ad account, optionally by campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            validated_account_id = extract_id_from_urn(account_id)
            campaign_id = inputs.get("campaign_id", "")
            page_size = inputs.get("page_size", 25)
            page_token = inputs.get("page_token")

            # The criteria finder uses cursor-based pagination (pageSize/pageToken)
            # from API version 202401; the old index-based `count` is ignored.
            params = {"q": "criteria", "pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            if campaign_id:
                campaign_urn = build_urn("campaign", extract_id_from_urn(campaign_id))
                params["campaigns"] = f"List({urn_param(campaign_urn)})"

            # Creatives are now retrieved via the account-scoped `criteria`
            # finder, optionally filtered by campaign. The criteria finder
            # requires the Rest.li FINDER method header per LinkedIn's docs.
            data = await li_fetch(
                context,
                "GET",
                f"/adAccounts/{validated_account_id}/creatives",
                params=params,
                extra_headers={"X-RestLi-Method": "FINDER"},
            )

            creatives = (data or {}).get("elements", [])
            next_page_token = ((data or {}).get("metadata") or {}).get("nextPageToken")
            return ActionResult(data={"creatives": creatives, "next_page_token": next_page_token}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_ad_analytics")
class GetAdAnalyticsAction(ActionHandler):
    """Retrieve performance analytics for campaigns."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            start_date = inputs["start_date"]
            end_date = inputs["end_date"]

            validated_id = extract_id_from_urn(account_id)
            account_urn = build_urn("account", validated_id)
            campaign_ids = inputs.get("campaign_ids", [])
            time_granularity = inputs.get("time_granularity", "DAILY")

            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return ActionError(message="Invalid date format. Use YYYY-MM-DD")

            date_range = (
                f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),"
                f"end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
            )

            params = {
                "q": "analytics",
                "pivot": "CAMPAIGN",
                "dateRange": date_range,
                "timeGranularity": time_granularity,
                "accounts": f"List({urn_param(account_urn)})",
                "fields": ANALYTICS_FIELDS,
            }

            if campaign_ids:
                campaign_urns = ",".join(
                    urn_param(build_urn("campaign", extract_id_from_urn(cid))) for cid in campaign_ids
                )
                params["campaigns"] = f"List({campaign_urns})"

            data = await li_fetch(context, "GET", "/adAnalytics", params=params)

            analytics = (data or {}).get("elements", [])
            return ActionResult(data={"analytics": analytics}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@linkedin_ads.action("get_ad_account_users")
class GetAdAccountUsersAction(ActionHandler):
    """Retrieve users with access to an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            account_id = inputs["account_id"]
            validated_id = extract_id_from_urn(account_id)
            account_urn = build_urn("account", validated_id)

            params = {"q": "accounts", "accounts": f"List({urn_param(account_urn)})"}

            data = await li_fetch(context, "GET", "/adAccountUsers", params=params)

            users = (data or {}).get("elements", [])
            return ActionResult(data={"users": users}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
