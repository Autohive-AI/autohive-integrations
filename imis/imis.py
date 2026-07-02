from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Any, Dict, Optional
from urllib.parse import urlencode, quote, urlparse

imis = Integration.load()


def _encode_id(value: Any) -> str:
    return quote(str(value), safe="")


def _validate_site_url(site_url: str) -> str:
    parsed = urlparse(site_url)
    if parsed.scheme != "https":
        raise ValueError("site_url must use HTTPS")
    if not parsed.hostname:
        raise ValueError("site_url must include a valid hostname")
    if parsed.username or parsed.password:
        raise ValueError("site_url must not include credentials")
    return site_url.rstrip("/")


async def get_access_token(context: ExecutionContext) -> str:
    creds = context.auth.get("credentials", context.auth)
    site_url = _validate_site_url(creds.get("site_url", ""))
    username = creds.get("username", "")
    password = creds.get("password", "")
    client_id = creds.get("client_id", "iMIS")

    body = urlencode(
        {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
        }
    )

    resp = await context.fetch(
        f"{site_url}/token/",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body,
    )

    if not isinstance(resp.data, dict) or "access_token" not in resp.data:
        raise Exception(f"Failed to obtain iMIS access token: {resp.data}")

    return resp.data["access_token"]


async def api_request(
    context: ExecutionContext,
    method: str,
    path: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    creds = context.auth.get("credentials", context.auth)
    site_url = _validate_site_url(creds.get("site_url", ""))
    access_token = await get_access_token(context)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = await context.fetch(
        f"{site_url}/api/{path.lstrip('/')}",
        method=method,
        headers=headers,
        json=json_data,
        params=params,
    )
    return resp.data


# ---- Contacts ----


@imis.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("name"):
                params["Name"] = inputs["name"]
            if inputs.get("email"):
                params["Email"] = inputs["email"]
            if inputs.get("member_type"):
                params["MemberTypeCode"] = inputs["member_type"]
            if inputs.get("status"):
                params["StatusCode"] = inputs["status"]

            data = await api_request(context, "GET", "Party", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"contacts": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            party_id = _encode_id(inputs["party_id"])
            data = await api_request(context, "GET", f"Party/{party_id}")
            return ActionResult(data={"contact": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            party_id = _encode_id(inputs["party_id"])

            # First fetch existing contact to use as base
            existing = await api_request(context, "GET", f"Party/{party_id}")

            # Apply updates
            if inputs.get("first_name"):
                existing["FirstName"] = inputs["first_name"]
            if inputs.get("last_name"):
                existing["LastName"] = inputs["last_name"]
            if inputs.get("email"):
                existing["PrimaryEmail"] = inputs["email"]
            if inputs.get("phone"):
                existing["PrimaryPhone"] = inputs["phone"]
            if inputs.get("address"):
                addr = inputs["address"]
                existing.setdefault("PrimaryAddress", {})
                if addr.get("line1"):
                    existing["PrimaryAddress"]["AddressLine1"] = addr["line1"]
                if addr.get("line2"):
                    existing["PrimaryAddress"]["AddressLine2"] = addr["line2"]
                if addr.get("city"):
                    existing["PrimaryAddress"]["City"] = addr["city"]
                if addr.get("state"):
                    existing["PrimaryAddress"]["StateProvince"] = addr["state"]
                if addr.get("zip"):
                    existing["PrimaryAddress"]["Zip"] = addr["zip"]
                if addr.get("country"):
                    existing["PrimaryAddress"]["Country"] = addr["country"]
            if inputs.get("additional_fields"):
                existing.update({k: v for k, v in inputs["additional_fields"].items() if k not in ("Id", "$type")})

            data = await api_request(context, "PUT", f"Party/{party_id}", json_data=existing)
            return ActionResult(data={"contact": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Events ----


@imis.action("list_events")
class ListEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("from_date"):
                params["FromDate"] = inputs["from_date"]
            if inputs.get("to_date"):
                params["ToDate"] = inputs["to_date"]

            data = await api_request(context, "GET", "Event", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"events": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("get_event")
class GetEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_id = _encode_id(inputs["event_id"])
            data = await api_request(context, "GET", f"Event/{event_id}")
            return ActionResult(data={"event": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("create_event")
class CreateEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body: Dict[str, Any] = {
                "Title": inputs["title"],
                "StartDate": inputs["start_date"],
            }
            if inputs.get("end_date"):
                body["EndDate"] = inputs["end_date"]
            if inputs.get("description"):
                body["Description"] = inputs["description"]
            if inputs.get("location"):
                body["Location"] = inputs["location"]
            if inputs.get("capacity"):
                body["Capacity"] = inputs["capacity"]
            if inputs.get("additional_fields"):
                body.update({k: v for k, v in inputs["additional_fields"].items() if k not in ("Id", "$type")})

            data = await api_request(context, "POST", "Event", json_data=body)
            return ActionResult(data={"event": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("update_event")
class UpdateEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_id = _encode_id(inputs["event_id"])

            # Fetch existing event as base
            existing = await api_request(context, "GET", f"Event/{event_id}")

            if inputs.get("title"):
                existing["Title"] = inputs["title"]
            if inputs.get("start_date"):
                existing["StartDate"] = inputs["start_date"]
            if inputs.get("end_date"):
                existing["EndDate"] = inputs["end_date"]
            if inputs.get("description"):
                existing["Description"] = inputs["description"]
            if inputs.get("location"):
                existing["Location"] = inputs["location"]
            if inputs.get("capacity"):
                existing["Capacity"] = inputs["capacity"]
            if inputs.get("additional_fields"):
                existing.update({k: v for k, v in inputs["additional_fields"].items() if k not in ("Id", "$type")})

            data = await api_request(context, "PUT", f"Event/{event_id}", json_data=existing)
            return ActionResult(data={"event": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Event Registrations ----


@imis.action("list_registrations")
class ListRegistrationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("event_id"):
                params["EventId"] = inputs["event_id"]
            if inputs.get("party_id"):
                params["PartyId"] = inputs["party_id"]

            data = await api_request(context, "GET", "EventRegistration", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"registrations": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("create_registration")
class CreateRegistrationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body: Dict[str, Any] = {
                "$type": "Asi.Soa.Commerce.DataContracts.EventRegistrationData, Asi.Contracts",
                "EventId": inputs["event_id"],
                "ContactId": inputs["party_id"],
                "OperationName": "RegisterEvent",
            }
            if inputs.get("additional_fields"):
                body.update(
                    {k: v for k, v in inputs["additional_fields"].items() if k not in ("Id", "$type", "OperationName")}
                )

            data = await api_request(context, "POST", "EventRegistration/_execute", json_data=body)
            return ActionResult(data={"registration": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Contacts (extended) ----


@imis.action("create_contact")
class CreateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body: Dict[str, Any] = {
                "$type": "Asi.Soa.Membership.DataContracts.PersonData, Asi.Contracts",
                "PersonName": {
                    "FirstName": inputs.get("first_name", ""),
                    "LastName": inputs["last_name"],
                },
                "PrimaryEmail": inputs.get("email", ""),
            }
            if inputs.get("phone"):
                body["PrimaryPhone"] = inputs["phone"]
            if inputs.get("address"):
                addr = inputs["address"]
                body["PrimaryAddress"] = {
                    "AddressLine1": addr.get("line1", ""),
                    "AddressLine2": addr.get("line2", ""),
                    "City": addr.get("city", ""),
                    "StateProvince": addr.get("state", ""),
                    "Zip": addr.get("zip", ""),
                    "Country": addr.get("country", ""),
                }
            if inputs.get("additional_fields"):
                body.update({k: v for k, v in inputs["additional_fields"].items() if k not in ("Id", "$type")})

            data = await api_request(context, "POST", "Party", json_data=body)
            return ActionResult(data={"contact": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Groups ----


@imis.action("list_groups")
class ListGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            data = await api_request(context, "GET", "Group", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"groups": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("get_group")
class GetGroupAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = await api_request(context, "GET", f"Group/{_encode_id(inputs['group_id'])}")
            return ActionResult(data={"group": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("add_group_member")
class AddGroupMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"GroupId": inputs["group_id"], "PartyId": inputs["party_id"]}
            data = await api_request(context, "POST", "GroupMember", json_data=body)
            return ActionResult(data={"member": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("remove_group_member")
class RemoveGroupMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            await api_request(
                context,
                "DELETE",
                f"GroupMember/{_encode_id(inputs['group_id'])}/{_encode_id(inputs['party_id'])}",
            )
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Event Registrations (extended) ----


@imis.action("delete_registration")
class DeleteRegistrationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            await api_request(context, "DELETE", f"EventRegistration/{_encode_id(inputs['registration_id'])}")
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Tags ----


@imis.action("list_tags")
class ListTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 100),
                "offset": inputs.get("offset", 0),
            }
            data = await api_request(context, "GET", "Tag", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"tags": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("add_tag")
class AddTagAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"PartyId": inputs["party_id"], "Tag": inputs["tag"]}
            data = await api_request(context, "POST", "Tag", json_data=body)
            return ActionResult(data={"tag": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- IQA Queries ----


@imis.action("run_query")
class RunQueryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            query_name = inputs["query_name"]
            params: Dict[str, Any] = {"QueryName": query_name}
            if inputs.get("limit"):
                params["Limit"] = inputs["limit"]
            if inputs.get("offset"):
                params["Offset"] = inputs["offset"]
            if inputs.get("parameters"):
                params.update(inputs["parameters"])

            data = await api_request(context, "GET", "Query", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"results": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Media Assets ----


@imis.action("list_media_assets")
class ListMediaAssetsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {
                "limit": inputs.get("limit", 20),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("search"):
                params["Name"] = inputs["search"]

            data = await api_request(context, "GET", "MediaAsset", params=params)
            items = data.get("Items", []) if isinstance(data, dict) else []
            count = data.get("TotalCount", data.get("Count", len(items))) if isinstance(data, dict) else len(items)
            return ActionResult(data={"assets": items, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@imis.action("get_media_asset")
class GetMediaAssetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = await api_request(context, "GET", f"MediaAsset/{_encode_id(inputs['asset_id'])}")
            return ActionResult(data={"asset": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
