import urllib.parse

import yarl

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    HTTPError,
    RateLimitError,
)
from typing import Dict, Any, Optional
from datetime import datetime

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


async def make_request(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Make a request to the LinkedIn Marketing API.

    Returns ``{"success": True, "data": <parsed body>}`` on success (the
    ``FetchResponse`` wrapper is unwrapped to its ``.data`` body), or
    ``{"success": False, "error": ..., "details": ...}`` on failure.
    """
    headers = get_headers()
    if extra_headers:
        headers.update(extra_headers)

    url = f"{API_BASE_URL}{endpoint}"
    if params:
        url = f"{url}?{build_query(params)}"

    # Pass a pre-encoded yarl.URL so aiohttp sends our query verbatim. With the
    # default (encoded=False) aiohttp re-canonicalizes the URL and decodes the
    # %3A in URN tokens back to literal colons, which LinkedIn's Rest.li parser
    # rejects with ILLEGAL_ARGUMENT inside List(...) finder values.
    request_url = yarl.URL(url, encoded=True)

    try:
        if method == "GET":
            response = await context.fetch(request_url, headers=headers)
        elif method == "POST":
            response = await context.fetch(request_url, method="POST", json=json_body, headers=headers)
        elif method == "DELETE":
            response = await context.fetch(request_url, method="DELETE", headers=headers)
        else:
            return {"success": False, "error": f"Unsupported HTTP method: {method}"}

        # context.fetch returns a FetchResponse(status, headers, data); unwrap
        # to the parsed body. Fall back to the response itself for test doubles
        # that return the body directly.
        data = getattr(response, "data", response)
        return {"success": True, "data": data}
    except RateLimitError as e:
        return {
            "success": False,
            "error": "Rate limit exceeded - try again later",
            "details": {"status": e.status, "response": e.response_data},
        }
    except HTTPError as e:
        friendly = {
            401: "Unauthorized - check your access token",
            403: "Forbidden - insufficient permissions",
            404: "Resource not found",
        }.get(e.status)
        error = f"{friendly} (HTTP {e.status})" if friendly else f"HTTP {e.status}: {e.message}"
        return {
            "success": False,
            "error": error,
            "details": {"status": e.status, "response": e.response_data},
        }
    except Exception as e:
        error_message = str(e)
        return {"success": False, "error": error_message, "details": {"raw_error": error_message}}


@linkedin_ads.action("get_ad_accounts")
class GetAdAccountsAction(ActionHandler):
    """Retrieve all ad accounts the authenticated user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            page_size = inputs.get("page_size", 25)

            result = await make_request(
                context,
                "GET",
                "/adAccountUsers",
                params={"q": "authenticatedUser", "count": page_size},
            )

            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "accounts": []},
                    cost_usd=0.0,
                )

            elements = (result["data"] or {}).get("elements", [])

            account_ids = []
            for element in elements:
                account_urn = element.get("account")
                if account_urn:
                    try:
                        account_ids.append(extract_id_from_urn(account_urn))
                    except ValueError:
                        continue

            if not account_ids:
                return ActionResult(data={"result": True, "accounts": []}, cost_usd=0.0)

            # The versioned API does not support BATCH_GET on /adAccounts
            # (ids=List(...) returns 404 RESOURCE_NOT_FOUND), so fetch each
            # account individually via GET /adAccounts/{id}.
            accounts = []
            for account_id in account_ids:
                acct_result = await make_request(context, "GET", f"/adAccounts/{account_id}")
                if acct_result["success"] and acct_result["data"]:
                    accounts.append(acct_result["data"])

            return ActionResult(data={"result": True, "accounts": accounts}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e), "accounts": []}, cost_usd=0.0)


@linkedin_ads.action("get_campaigns")
class GetCampaignsAction(ActionHandler):
    """Retrieve campaigns for a specific ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={
                        "result": False,
                        "error": "account_id is required",
                        "campaigns": [],
                    },
                    cost_usd=0.0,
                )

            try:
                validated_id = extract_id_from_urn(account_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "campaigns": []},
                    cost_usd=0.0,
                )
            status = inputs.get("status")
            page_size = inputs.get("page_size", 25)

            params = {"q": "search", "count": page_size}

            if status:
                params["search"] = f"(status:(values:List({status})))"

            # Campaign endpoints are now account-scoped: the account id lives in
            # the URL path, not the query.
            result = await make_request(context, "GET", f"/adAccounts/{validated_id}/adCampaigns", params=params)

            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "campaigns": []},
                    cost_usd=0.0,
                )

            campaigns = (result["data"] or {}).get("elements", [])
            return ActionResult(
                data={"result": True, "campaigns": campaigns, "total": len(campaigns)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e), "campaigns": []}, cost_usd=0.0)


@linkedin_ads.action("get_campaign")
class GetCampaignAction(ActionHandler):
    """Retrieve detailed information about a specific campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            account_id = inputs.get("account_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0,
                )
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required"},
                    cost_usd=0.0,
                )

            try:
                account_numeric_id = extract_id_from_urn(account_id)
                numeric_id = extract_id_from_urn(campaign_id)
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

            # Campaign endpoints are now account-scoped.
            result = await make_request(context, "GET", f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}")

            if not result["success"]:
                return ActionResult(data={"result": False, "error": result["error"]}, cost_usd=0.0)

            return ActionResult(data={"result": True, "campaign": result["data"]}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@linkedin_ads.action("create_campaign")
class CreateCampaignAction(ActionHandler):
    """Create a new advertising campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            campaign_group_id = inputs.get("campaign_group_id", "")
            name = inputs.get("name", "")
            objective_type = inputs.get("objective_type", "")
            campaign_type = inputs.get("type", "")
            daily_budget = inputs.get("daily_budget_amount")
            currency_code = inputs.get("currency_code", "USD")
            status = inputs.get("status", "DRAFT")
            cost_type = inputs.get("cost_type")
            unit_cost_amount = inputs.get("unit_cost_amount")

            if not all(
                [
                    account_id,
                    campaign_group_id,
                    name,
                    objective_type,
                    campaign_type,
                    daily_budget,
                ]
            ):
                return ActionResult(
                    data={"result": False, "error": "Missing required fields"},
                    cost_usd=0.0,
                )

            try:
                account_numeric_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", account_numeric_id)
                campaign_group_urn = build_urn("campaign_group", extract_id_from_urn(campaign_group_id))
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

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
            }

            if cost_type:
                campaign_data["costType"] = cost_type
            if unit_cost_amount is not None:
                campaign_data["unitCost"] = {
                    "amount": str(unit_cost_amount),
                    "currencyCode": currency_code,
                }

            # Campaign endpoints are now account-scoped.
            result = await make_request(
                context, "POST", f"/adAccounts/{account_numeric_id}/adCampaigns", json_body=campaign_data
            )

            if not result["success"]:
                return ActionResult(data={"result": False, "error": result["error"]}, cost_usd=0.0)

            campaign_id = (result["data"] or {}).get("id", "")
            return ActionResult(
                data={
                    "result": True,
                    "campaign_id": campaign_id,
                    "campaign": result["data"],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@linkedin_ads.action("update_campaign")
class UpdateCampaignAction(ActionHandler):
    """Update an existing campaign's settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            account_id = inputs.get("account_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0,
                )
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required"},
                    cost_usd=0.0,
                )

            try:
                account_numeric_id = extract_id_from_urn(account_id)
                numeric_id = extract_id_from_urn(campaign_id)
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

            patch_data = {"patch": {"$set": {}}}

            if inputs.get("name"):
                patch_data["patch"]["$set"]["name"] = inputs["name"]
            if inputs.get("status"):
                patch_data["patch"]["$set"]["status"] = inputs["status"]
            if inputs.get("daily_budget_amount"):
                patch_data["patch"]["$set"]["dailyBudget"] = {
                    "amount": str(inputs["daily_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD"),
                }
            if inputs.get("total_budget_amount"):
                patch_data["patch"]["$set"]["totalBudget"] = {
                    "amount": str(inputs["total_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD"),
                }

            if not patch_data["patch"]["$set"]:
                return ActionResult(
                    data={"result": False, "error": "No update fields provided"},
                    cost_usd=0.0,
                )

            # Campaign endpoints are now account-scoped.
            result = await make_request(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            if not result["success"]:
                return ActionResult(data={"result": False, "error": result["error"]}, cost_usd=0.0)

            return ActionResult(
                data={"result": True, "message": "Campaign updated successfully"},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@linkedin_ads.action("pause_campaign")
class PauseCampaignAction(ActionHandler):
    """Pause an active campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            account_id = inputs.get("account_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0,
                )
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required"},
                    cost_usd=0.0,
                )

            try:
                account_numeric_id = extract_id_from_urn(account_id)
                numeric_id = extract_id_from_urn(campaign_id)
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

            patch_data = {"patch": {"$set": {"status": "PAUSED"}}}

            # Campaign endpoints are now account-scoped.
            result = await make_request(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            if not result["success"]:
                return ActionResult(data={"result": False, "error": result["error"]}, cost_usd=0.0)

            return ActionResult(
                data={"result": True, "message": "Campaign paused successfully"},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@linkedin_ads.action("activate_campaign")
class ActivateCampaignAction(ActionHandler):
    """Activate a paused or draft campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            account_id = inputs.get("account_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0,
                )
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required"},
                    cost_usd=0.0,
                )

            try:
                account_numeric_id = extract_id_from_urn(account_id)
                numeric_id = extract_id_from_urn(campaign_id)
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

            patch_data = {"patch": {"$set": {"status": "ACTIVE"}}}

            # Campaign endpoints are now account-scoped.
            result = await make_request(
                context,
                "POST",
                f"/adAccounts/{account_numeric_id}/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
            )

            if not result["success"]:
                return ActionResult(data={"result": False, "error": result["error"]}, cost_usd=0.0)

            return ActionResult(
                data={"result": True, "message": "Campaign activated successfully"},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@linkedin_ads.action("get_campaign_groups")
class GetCampaignGroupsAction(ActionHandler):
    """Retrieve campaign groups for an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={
                        "result": False,
                        "error": "account_id is required",
                        "campaign_groups": [],
                    },
                    cost_usd=0.0,
                )

            try:
                validated_id = extract_id_from_urn(account_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "campaign_groups": []},
                    cost_usd=0.0,
                )
            status = inputs.get("status")

            params = {"q": "search", "count": 25}

            if status:
                params["search"] = f"(status:(values:List({status})))"

            # Campaign group endpoints are now account-scoped.
            result = await make_request(context, "GET", f"/adAccounts/{validated_id}/adCampaignGroups", params=params)

            if not result["success"]:
                return ActionResult(
                    data={
                        "result": False,
                        "error": result["error"],
                        "campaign_groups": [],
                    },
                    cost_usd=0.0,
                )

            campaign_groups = (result["data"] or {}).get("elements", [])
            return ActionResult(data={"result": True, "campaign_groups": campaign_groups}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "campaign_groups": []},
                cost_usd=0.0,
            )


@linkedin_ads.action("get_creatives")
class GetCreativesAction(ActionHandler):
    """Retrieve creatives (ads) for a campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={
                        "result": False,
                        "error": "account_id is required",
                        "creatives": [],
                    },
                    cost_usd=0.0,
                )

            campaign_id = inputs.get("campaign_id", "")
            try:
                validated_account_id = extract_id_from_urn(account_id)
                params = {"q": "criteria", "count": 25}
                if campaign_id:
                    campaign_urn = build_urn("campaign", extract_id_from_urn(campaign_id))
                    params["campaigns"] = f"List({urn_param(campaign_urn)})"
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "creatives": []},
                    cost_usd=0.0,
                )

            # Creatives are now retrieved via the account-scoped `criteria`
            # finder, optionally filtered by campaign.
            result = await make_request(context, "GET", f"/adAccounts/{validated_account_id}/creatives", params=params)

            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "creatives": []},
                    cost_usd=0.0,
                )

            creatives = (result["data"] or {}).get("elements", [])
            return ActionResult(data={"result": True, "creatives": creatives}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e), "creatives": []}, cost_usd=0.0)


@linkedin_ads.action("get_ad_analytics")
class GetAdAnalyticsAction(ActionHandler):
    """Retrieve performance analytics for campaigns."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            start_date = inputs.get("start_date", "")
            end_date = inputs.get("end_date", "")

            if not all([account_id, start_date, end_date]):
                return ActionResult(
                    data={
                        "result": False,
                        "error": "account_id, start_date, and end_date are required",
                        "analytics": [],
                    },
                    cost_usd=0.0,
                )

            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "analytics": []},
                    cost_usd=0.0,
                )
            campaign_ids = inputs.get("campaign_ids", [])
            time_granularity = inputs.get("time_granularity", "DAILY")

            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return ActionResult(
                    data={
                        "result": False,
                        "error": "Invalid date format. Use YYYY-MM-DD",
                        "analytics": [],
                    },
                    cost_usd=0.0,
                )

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

            result = await make_request(context, "GET", "/adAnalytics", params=params)

            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "analytics": []},
                    cost_usd=0.0,
                )

            analytics = (result["data"] or {}).get("elements", [])
            return ActionResult(data={"result": True, "analytics": analytics}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e), "analytics": []}, cost_usd=0.0)


@linkedin_ads.action("get_ad_account_users")
class GetAdAccountUsersAction(ActionHandler):
    """Retrieve users with access to an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={
                        "result": False,
                        "error": "account_id is required",
                        "users": [],
                    },
                    cost_usd=0.0,
                )

            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(data={"result": False, "error": str(e), "users": []}, cost_usd=0.0)

            params = {"q": "accounts", "accounts": f"List({urn_param(account_urn)})"}

            result = await make_request(context, "GET", "/adAccountUsers", params=params)

            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "users": []},
                    cost_usd=0.0,
                )

            users = (result["data"] or {}).get("elements", [])
            return ActionResult(data={"result": True, "users": users}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e), "users": []}, cost_usd=0.0)
