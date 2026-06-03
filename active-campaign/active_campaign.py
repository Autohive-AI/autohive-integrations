import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(__file__))

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

active_campaign = Integration.load()


def _base_url(context: ExecutionContext) -> str:
    api_url = context.auth.get("api_url", "").rstrip("/")
    return f"{api_url}/api/3"


def _headers(context: ExecutionContext) -> Dict[str, str]:
    api_key = context.auth.get("api_key", "")
    return {"Api-Token": api_key, "Accept": "application/json"}


def _raise_for_status(response: Any) -> None:
    if response.status >= 400:
        data = response.data or {}
        msg = data.get("message") or data.get("error") or f"HTTP {response.status}"
        raise ValueError(msg)


def _derive_rates(campaign: Dict[str, Any]) -> Dict[str, Any]:
    sends = int(campaign.get("send_amt") or 0)
    opens = int(campaign.get("uniqueopens") or 0)
    clicks = int(campaign.get("uniquelinkclicks") or 0)
    hard_bounces = int(campaign.get("hardbounces") or 0)
    soft_bounces = int(campaign.get("softbounces") or 0)
    bounces = hard_bounces + soft_bounces
    return {
        **campaign,
        "sends": sends,
        "open_rate": round(opens / sends * 100, 2) if sends else 0.0,
        "click_rate": round(clicks / sends * 100, 2) if sends else 0.0,
        "bounce_rate": round(bounces / sends * 100, 2) if sends else 0.0,
    }


# ---- Campaigns ----


@active_campaign.action("list_campaigns")
class ListCampaignsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("status") is not None:
                params["filters[status]"] = inputs["status"]
            if inputs.get("type"):
                params["filters[type]"] = inputs["type"]

            response = await context.fetch(
                f"{_base_url(context)}/campaigns",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            _raise_for_status(response)
            data = response.data or {}
            campaigns = [_derive_rates(c) for c in data.get("campaigns", [])]
            return ActionResult(
                data={
                    "result": True,
                    "campaigns": campaigns,
                    "total": int(data.get("meta", {}).get("total", 0)),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@active_campaign.action("get_campaign")
class GetCampaignAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs["campaign_id"]
            response = await context.fetch(
                f"{_base_url(context)}/campaigns/{campaign_id}",
                method="GET",
                headers=_headers(context),
            )
            _raise_for_status(response)
            campaign = (response.data or {}).get("campaign", response.data)
            return ActionResult(
                data={"result": True, "campaign": _derive_rates(campaign)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@active_campaign.action("get_campaign_links")
class GetCampaignLinksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            campaign_id = inputs["campaign_id"]
            response = await context.fetch(
                f"{_base_url(context)}/campaigns/{campaign_id}/links",
                method="GET",
                headers=_headers(context),
            )
            _raise_for_status(response)
            data = response.data or {}
            return ActionResult(
                data={
                    "result": True,
                    "links": data.get("links", []),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ---- Contacts ----


@active_campaign.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("email"):
                params["email"] = inputs["email"]
            if inputs.get("search"):
                params["search"] = inputs["search"]
            if inputs.get("listid"):
                params["listid"] = inputs["listid"]
            if inputs.get("status") is not None:
                params["status"] = inputs["status"]
            if inputs.get("created_after"):
                params["filters[created_after]"] = inputs["created_after"]
            if inputs.get("created_before"):
                params["filters[created_before]"] = inputs["created_before"]

            response = await context.fetch(
                f"{_base_url(context)}/contacts",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            _raise_for_status(response)
            data = response.data or {}
            return ActionResult(
                data={
                    "result": True,
                    "contacts": data.get("contacts", []),
                    "total": int(data.get("meta", {}).get("total", 0)),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@active_campaign.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            response = await context.fetch(
                f"{_base_url(context)}/contacts/{contact_id}",
                method="GET",
                headers=_headers(context),
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "contact": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@active_campaign.action("list_contact_activities")
class ListContactActivitiesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {"contact": inputs["contact_id"]}
            if inputs.get("after"):
                params["after"] = inputs["after"]
            if inputs.get("include_emails"):
                params["emails"] = "true"

            response = await context.fetch(
                f"{_base_url(context)}/activities",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            _raise_for_status(response)
            data = response.data or {}
            return ActionResult(
                data={
                    "result": True,
                    "activities": data.get("activities", []),
                    "total": int(data.get("meta", {}).get("total", 0)),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ---- Lists ----


@active_campaign.action("list_lists")
class ListListsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            response = await context.fetch(
                f"{_base_url(context)}/lists",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            _raise_for_status(response)
            data = response.data or {}
            return ActionResult(
                data={
                    "result": True,
                    "lists": data.get("lists", []),
                    "total": int(data.get("meta", {}).get("total", 0)),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))
