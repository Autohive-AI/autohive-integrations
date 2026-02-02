from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, Optional, List
from datetime import datetime

linkedin_ads = Integration.load()

# LinkedIn Marketing API Configuration
API_BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202601"


def get_headers() -> Dict[str, str]:
    """Build headers for LinkedIn Marketing API requests."""
    return {
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }


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
        "creative": "urn:li:sponsoredCreative"
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
    extra_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Make a request to the LinkedIn Marketing API."""
    headers = get_headers()
    if extra_headers:
        headers.update(extra_headers)
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = await context.fetch(url, params=params, headers=headers)
        elif method == "POST":
            response = await context.fetch(url, method="POST", json=json_body, headers=headers)
        elif method == "DELETE":
            response = await context.fetch(url, method="DELETE", headers=headers)
        else:
            return {"success": False, "error": f"Unsupported HTTP method: {method}"}
        
        return {"success": True, "data": response}
    except Exception as e:
        error_message = str(e)
        error_details = {"raw_error": error_message}
        
        if hasattr(e, 'status_code'):
            status_code = e.status_code
            if status_code == 401:
                return {"success": False, "error": "Unauthorized - check your access token", "details": error_details}
            elif status_code == 403:
                return {"success": False, "error": "Forbidden - insufficient permissions", "details": error_details}
            elif status_code == 404:
                return {"success": False, "error": "Resource not found", "details": error_details}
            elif status_code == 429:
                return {"success": False, "error": "Rate limit exceeded - try again later", "details": error_details}
        
        return {"success": False, "error": error_message, "details": error_details}


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
                params={
                    "q": "authenticatedUser",
                    "count": page_size
                }
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "accounts": []},
                    cost_usd=0.0
                )
            
            elements = result["data"].get("elements", [])
            
            account_ids = []
            for element in elements:
                account_urn = element.get("account")
                if account_urn:
                    try:
                        account_ids.append(extract_id_from_urn(account_urn))
                    except ValueError:
                        continue
            
            if not account_ids:
                return ActionResult(
                    data={"result": True, "accounts": []},
                    cost_usd=0.0
                )
            
            ids_param = ",".join(account_ids)
            batch_result = await make_request(
                context,
                "GET",
                "/adAccounts",
                params={"ids": f"List({ids_param})"}
            )
            
            if not batch_result["success"]:
                return ActionResult(
                    data={"result": False, "error": batch_result["error"], "accounts": []},
                    cost_usd=0.0
                )
            
            accounts = batch_result["data"].get("results", {})
            account_list = list(accounts.values()) if isinstance(accounts, dict) else accounts
            
            return ActionResult(
                data={"result": True, "accounts": account_list},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "accounts": []},
                cost_usd=0.0
            )


@linkedin_ads.action("get_campaigns")
class GetCampaignsAction(ActionHandler):
    """Retrieve campaigns for a specific ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required", "campaigns": []},
                    cost_usd=0.0
                )
            
            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "campaigns": []},
                    cost_usd=0.0
                )
            status = inputs.get("status")
            page_size = inputs.get("page_size", 25)
            
            params = {
                "q": "search",
                "search.account.values[0]": account_urn,
                "count": page_size
            }
            
            if status:
                params["search.status.values[0]"] = status
            
            result = await make_request(context, "GET", "/adCampaigns", params=params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "campaigns": []},
                    cost_usd=0.0
                )
            
            campaigns = result["data"].get("elements", [])
            return ActionResult(
                data={"result": True, "campaigns": campaigns, "total": len(campaigns)},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "campaigns": []},
                cost_usd=0.0
            )


@linkedin_ads.action("get_campaign")
class GetCampaignAction(ActionHandler):
    """Retrieve detailed information about a specific campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0
                )
            
            numeric_id = extract_id_from_urn(campaign_id)
            result = await make_request(context, "GET", f"/adCampaigns/{numeric_id}")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "campaign": result["data"]},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


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
            
            if not all([account_id, campaign_group_id, name, objective_type, campaign_type, daily_budget]):
                return ActionResult(
                    data={"result": False, "error": "Missing required fields"},
                    cost_usd=0.0
                )
            
            try:
                account_urn = build_urn("account", extract_id_from_urn(account_id))
                campaign_group_urn = build_urn("campaign_group", extract_id_from_urn(campaign_group_id))
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e)},
                    cost_usd=0.0
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
                    "currencyCode": currency_code
                }
            }
            
            if cost_type:
                campaign_data["costType"] = cost_type
            if unit_cost_amount is not None:
                campaign_data["unitCost"] = {
                    "amount": str(unit_cost_amount),
                    "currencyCode": currency_code
                }
            
            result = await make_request(
                context,
                "POST",
                "/adCampaigns",
                json_body=campaign_data
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            campaign_id = result["data"].get("id", "")
            return ActionResult(
                data={"result": True, "campaign_id": campaign_id, "campaign": result["data"]},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@linkedin_ads.action("update_campaign")
class UpdateCampaignAction(ActionHandler):
    """Update an existing campaign's settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0
                )
            
            numeric_id = extract_id_from_urn(campaign_id)
            
            patch_data = {"patch": {"$set": {}}}
            
            if inputs.get("name"):
                patch_data["patch"]["$set"]["name"] = inputs["name"]
            if inputs.get("status"):
                patch_data["patch"]["$set"]["status"] = inputs["status"]
            if inputs.get("daily_budget_amount"):
                patch_data["patch"]["$set"]["dailyBudget"] = {
                    "amount": str(inputs["daily_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD")
                }
            if inputs.get("total_budget_amount"):
                patch_data["patch"]["$set"]["totalBudget"] = {
                    "amount": str(inputs["total_budget_amount"]),
                    "currencyCode": inputs.get("currency_code", "USD")
                }
            
            if not patch_data["patch"]["$set"]:
                return ActionResult(
                    data={"result": False, "error": "No update fields provided"},
                    cost_usd=0.0
                )
            
            result = await make_request(
                context,
                "POST",
                f"/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"}
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "message": "Campaign updated successfully"},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@linkedin_ads.action("pause_campaign")
class PauseCampaignAction(ActionHandler):
    """Pause an active campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0
                )
            
            numeric_id = extract_id_from_urn(campaign_id)
            
            patch_data = {"patch": {"$set": {"status": "PAUSED"}}}
            
            result = await make_request(
                context,
                "POST",
                f"/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"}
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "message": "Campaign paused successfully"},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@linkedin_ads.action("activate_campaign")
class ActivateCampaignAction(ActionHandler):
    """Activate a paused or draft campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required"},
                    cost_usd=0.0
                )
            
            numeric_id = extract_id_from_urn(campaign_id)
            
            patch_data = {"patch": {"$set": {"status": "ACTIVE"}}}
            
            result = await make_request(
                context,
                "POST",
                f"/adCampaigns/{numeric_id}",
                json_body=patch_data,
                extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"}
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "message": "Campaign activated successfully"},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@linkedin_ads.action("get_campaign_groups")
class GetCampaignGroupsAction(ActionHandler):
    """Retrieve campaign groups for an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required", "campaign_groups": []},
                    cost_usd=0.0
                )
            
            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "campaign_groups": []},
                    cost_usd=0.0
                )
            status = inputs.get("status")
            
            params = {
                "q": "search",
                "search.account.values[0]": account_urn
            }
            
            if status:
                params["search.status.values[0]"] = status
            
            result = await make_request(context, "GET", "/adCampaignGroups", params=params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "campaign_groups": []},
                    cost_usd=0.0
                )
            
            campaign_groups = result["data"].get("elements", [])
            return ActionResult(
                data={"result": True, "campaign_groups": campaign_groups},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "campaign_groups": []},
                cost_usd=0.0
            )


@linkedin_ads.action("get_creatives")
class GetCreativesAction(ActionHandler):
    """Retrieve creatives (ads) for a campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs.get("campaign_id", "")
            if not campaign_id:
                return ActionResult(
                    data={"result": False, "error": "campaign_id is required", "creatives": []},
                    cost_usd=0.0
                )
            
            try:
                validated_id = extract_id_from_urn(campaign_id)
                campaign_urn = build_urn("campaign", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "creatives": []},
                    cost_usd=0.0
                )
            
            params = {
                "q": "search",
                "search.campaign.values[0]": campaign_urn
            }
            
            result = await make_request(context, "GET", "/creatives", params=params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "creatives": []},
                    cost_usd=0.0
                )
            
            creatives = result["data"].get("elements", [])
            return ActionResult(
                data={"result": True, "creatives": creatives},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "creatives": []},
                cost_usd=0.0
            )


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
                    data={"result": False, "error": "account_id, start_date, and end_date are required", "analytics": []},
                    cost_usd=0.0
                )
            
            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "analytics": []},
                    cost_usd=0.0
                )
            campaign_ids = inputs.get("campaign_ids", [])
            time_granularity = inputs.get("time_granularity", "DAILY")
            
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return ActionResult(
                    data={"result": False, "error": "Invalid date format. Use YYYY-MM-DD", "analytics": []},
                    cost_usd=0.0
                )
            
            params = {
                "q": "analytics",
                "pivot": "CAMPAIGN",
                "dateRange.start.day": start_dt.day,
                "dateRange.start.month": start_dt.month,
                "dateRange.start.year": start_dt.year,
                "dateRange.end.day": end_dt.day,
                "dateRange.end.month": end_dt.month,
                "dateRange.end.year": end_dt.year,
                "timeGranularity": time_granularity,
                "accounts[0]": account_urn,
                "fields": "impressions,clicks,costInLocalCurrency,externalWebsiteConversions,costPerClick,clickThroughRate"
            }
            
            if campaign_ids:
                for i, cid in enumerate(campaign_ids):
                    params[f"campaigns[{i}]"] = build_urn("campaign", cid)
            
            result = await make_request(context, "GET", "/adAnalytics", params=params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "analytics": []},
                    cost_usd=0.0
                )
            
            analytics = result["data"].get("elements", [])
            return ActionResult(
                data={"result": True, "analytics": analytics},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "analytics": []},
                cost_usd=0.0
            )


@linkedin_ads.action("get_ad_account_users")
class GetAdAccountUsersAction(ActionHandler):
    """Retrieve users with access to an ad account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            account_id = inputs.get("account_id", "")
            if not account_id:
                return ActionResult(
                    data={"result": False, "error": "account_id is required", "users": []},
                    cost_usd=0.0
                )
            
            try:
                validated_id = extract_id_from_urn(account_id)
                account_urn = build_urn("account", validated_id)
            except ValueError as e:
                return ActionResult(
                    data={"result": False, "error": str(e), "users": []},
                    cost_usd=0.0
                )
            
            params = {
                "q": "account",
                "account": account_urn
            }
            
            result = await make_request(context, "GET", "/adAccountUsers", params=params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "users": []},
                    cost_usd=0.0
                )
            
            users = result["data"].get("elements", [])
            return ActionResult(
                data={"result": True, "users": users},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "users": []},
                cost_usd=0.0
            )
