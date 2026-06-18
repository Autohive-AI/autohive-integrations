from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, Optional

dynamics365 = Integration.load()

API_VERSION = "v9.2"
ODATA_HEADERS = {
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
    "Prefer": 'odata.include-annotations="*"',
}

TASK_PRIORITY_MAP = {"Low": 0, "Normal": 1, "High": 2}
REGARDING_TYPE_MAP = {
    "account": "accounts",
    "contact": "contacts",
    "opportunity": "opportunities",
    "lead": "leads",
}


def _base_url(context: ExecutionContext) -> str:
    org_url = context.auth.get("org_url", "").rstrip("/")
    return f"{org_url}/api/data/{API_VERSION}"


def _token(context: ExecutionContext) -> str:
    return context.auth.get("credentials", {}).get("access_token", "")


def _auth_headers(context: ExecutionContext) -> Dict[str, str]:
    return {**ODATA_HEADERS, "Authorization": f"Bearer {_token(context)}"}


def _check(data: Any) -> None:
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        raise ValueError(err.get("message") or str(err))


async def _get(context: ExecutionContext, path: str, params: Optional[Dict] = None) -> Any:
    url = f"{_base_url(context)}/{path}"
    resp = await context.fetch(url, method="GET", params=params, headers=_auth_headers(context))
    _check(resp.data if hasattr(resp, "data") else resp)
    return resp.data if hasattr(resp, "data") else resp


async def _post(context: ExecutionContext, path: str, body: Dict) -> Any:
    url = f"{_base_url(context)}/{path}"
    resp = await context.fetch(url, method="POST", json=body, headers={
        **_auth_headers(context), "Content-Type": "application/json"
    })
    _check(resp.data if hasattr(resp, "data") else resp)
    return resp.data if hasattr(resp, "data") else resp


async def _patch(context: ExecutionContext, path: str, body: Dict) -> None:
    url = f"{_base_url(context)}/{path}"
    resp = await context.fetch(url, method="PATCH", json=body, headers={
        **_auth_headers(context), "Content-Type": "application/json",
        "If-Match": "*",
    })
    data = resp.data if hasattr(resp, "data") else resp
    if data:
        _check(data)


def _build_filter(conditions: list) -> Optional[str]:
    parts = [c for c in conditions if c]
    return " and ".join(parts) if parts else None


# ---- Accounts ----

@dynamics365.action("list_accounts")
class ListAccountsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            if inputs.get("name"):
                filters.append(f"contains(name,'{inputs['name']}')")
            if inputs.get("industry"):
                filters.append(f"industrycode eq {inputs['industry']}")

            params: Dict[str, Any] = {"$top": inputs.get("limit", 20)}
            if inputs.get("select"):
                params["$select"] = inputs["select"]
            f = _build_filter(filters)
            if f:
                params["$filter"] = f

            data = await _get(context, "accounts", params)
            items = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"accounts": items, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("get_account")
class GetAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await _get(context, f"accounts({inputs['account_id']})")
            return ActionResult(data={"account": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("create_account")
class CreateAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {"name": inputs["name"]}
            if inputs.get("email"):
                body["emailaddress1"] = inputs["email"]
            if inputs.get("phone"):
                body["telephone1"] = inputs["phone"]
            if inputs.get("website"):
                body["websiteurl"] = inputs["website"]
            if inputs.get("industry"):
                body["industrycode"] = inputs["industry"]
            if inputs.get("city"):
                body["address1_city"] = inputs["city"]
            if inputs.get("country"):
                body["address1_country"] = inputs["country"]
            if inputs.get("description"):
                body["description"] = inputs["description"]

            data = await _post(context, "accounts", body)
            return ActionResult(data={"account": data or body}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("update_account")
class UpdateAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {}
            if inputs.get("name"):
                body["name"] = inputs["name"]
            if inputs.get("email"):
                body["emailaddress1"] = inputs["email"]
            if inputs.get("phone"):
                body["telephone1"] = inputs["phone"]
            if inputs.get("website"):
                body["websiteurl"] = inputs["website"]
            if inputs.get("description"):
                body["description"] = inputs["description"]

            await _patch(context, f"accounts({inputs['account_id']})", body)
            return ActionResult(data={"updated": True, "account_id": inputs["account_id"]}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Contacts ----

@dynamics365.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            if inputs.get("first_name"):
                filters.append(f"contains(firstname,'{inputs['first_name']}')")
            if inputs.get("last_name"):
                filters.append(f"contains(lastname,'{inputs['last_name']}')")
            if inputs.get("email"):
                filters.append(f"emailaddress1 eq '{inputs['email']}'")
            if inputs.get("account_id"):
                filters.append(f"_parentcustomerid_value eq {inputs['account_id']}")

            params: Dict[str, Any] = {"$top": inputs.get("limit", 20)}
            if inputs.get("select"):
                params["$select"] = inputs["select"]
            f = _build_filter(filters)
            if f:
                params["$filter"] = f

            data = await _get(context, "contacts", params)
            items = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"contacts": items, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await _get(context, f"contacts({inputs['contact_id']})")
            return ActionResult(data={"contact": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("create_contact")
class CreateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {"lastname": inputs["last_name"]}
            if inputs.get("first_name"):
                body["firstname"] = inputs["first_name"]
            if inputs.get("email"):
                body["emailaddress1"] = inputs["email"]
            if inputs.get("phone"):
                body["telephone1"] = inputs["phone"]
            if inputs.get("job_title"):
                body["jobtitle"] = inputs["job_title"]
            if inputs.get("account_id"):
                body["parentcustomerid_account@odata.bind"] = f"/accounts({inputs['account_id']})"
            if inputs.get("city"):
                body["address1_city"] = inputs["city"]
            if inputs.get("country"):
                body["address1_country"] = inputs["country"]

            data = await _post(context, "contacts", body)
            return ActionResult(data={"contact": data or body}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {}
            if inputs.get("first_name"):
                body["firstname"] = inputs["first_name"]
            if inputs.get("last_name"):
                body["lastname"] = inputs["last_name"]
            if inputs.get("email"):
                body["emailaddress1"] = inputs["email"]
            if inputs.get("phone"):
                body["telephone1"] = inputs["phone"]
            if inputs.get("job_title"):
                body["jobtitle"] = inputs["job_title"]

            await _patch(context, f"contacts({inputs['contact_id']})", body)
            return ActionResult(data={"updated": True, "contact_id": inputs["contact_id"]}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Leads ----

@dynamics365.action("list_leads")
class ListLeadsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            if inputs.get("first_name"):
                filters.append(f"contains(firstname,'{inputs['first_name']}')")
            if inputs.get("last_name"):
                filters.append(f"contains(lastname,'{inputs['last_name']}')")
            if inputs.get("email"):
                filters.append(f"emailaddress1 eq '{inputs['email']}'")
            if inputs.get("status"):
                filters.append(f"statuscode eq {inputs['status']}")

            params: Dict[str, Any] = {"$top": inputs.get("limit", 20)}
            f = _build_filter(filters)
            if f:
                params["$filter"] = f

            data = await _get(context, "leads", params)
            items = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"leads": items, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("get_lead")
class GetLeadAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await _get(context, f"leads({inputs['lead_id']})")
            return ActionResult(data={"lead": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("create_lead")
class CreateLeadAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "lastname": inputs["last_name"],
                "companyname": inputs["company"],
            }
            if inputs.get("first_name"):
                body["firstname"] = inputs["first_name"]
            if inputs.get("email"):
                body["emailaddress1"] = inputs["email"]
            if inputs.get("phone"):
                body["telephone1"] = inputs["phone"]
            if inputs.get("topic"):
                body["subject"] = inputs["topic"]
            if inputs.get("source"):
                body["leadsourcecode"] = inputs["source"]
            if inputs.get("description"):
                body["description"] = inputs["description"]

            data = await _post(context, "leads", body)
            return ActionResult(data={"lead": data or body}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("qualify_lead")
class QualifyLeadAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "CreateAccount": inputs.get("create_account", True),
                "CreateContact": inputs.get("create_contact", True),
                "CreateOpportunity": inputs.get("create_opportunity", False),
                "Status": 3,  # Qualified
            }
            data = await _post(context, f"leads({inputs['lead_id']})/Microsoft.Dynamics.CRM.QualifyLead", body)
            created = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"qualified": True, "created_entities": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Opportunities ----

@dynamics365.action("list_opportunities")
class ListOpportunitiesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            if inputs.get("name"):
                filters.append(f"contains(name,'{inputs['name']}')")
            if inputs.get("account_id"):
                filters.append(f"_parentaccountid_value eq {inputs['account_id']}")
            if inputs.get("status"):
                status_map = {"Open": 0, "Won": 1, "Lost": 2}
                code = status_map.get(inputs["status"], inputs["status"])
                filters.append(f"statecode eq {code}")

            params: Dict[str, Any] = {"$top": inputs.get("limit", 20)}
            f = _build_filter(filters)
            if f:
                params["$filter"] = f

            data = await _get(context, "opportunities", params)
            items = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"opportunities": items, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("get_opportunity")
class GetOpportunityAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await _get(context, f"opportunities({inputs['opportunity_id']})")
            return ActionResult(data={"opportunity": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("create_opportunity")
class CreateOpportunityAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {"name": inputs["name"]}
            if inputs.get("account_id"):
                body["parentaccountid_account@odata.bind"] = f"/accounts({inputs['account_id']})"
            if inputs.get("estimated_value") is not None:
                body["estimatedvalue"] = inputs["estimated_value"]
            if inputs.get("close_date"):
                body["estimatedclosedate"] = inputs["close_date"]
            if inputs.get("description"):
                body["description"] = inputs["description"]
            if inputs.get("probability") is not None:
                body["closeprobability"] = inputs["probability"]

            data = await _post(context, "opportunities", body)
            return ActionResult(data={"opportunity": data or body}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Tasks ----

@dynamics365.action("list_tasks")
class ListTasksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            if inputs.get("regarding_id"):
                filters.append(f"_regardingobjectid_value eq {inputs['regarding_id']}")
            if inputs.get("status"):
                status_map = {"Open": 0, "Completed": 1, "Cancelled": 2}
                code = status_map.get(inputs["status"], inputs["status"])
                filters.append(f"statecode eq {code}")

            params: Dict[str, Any] = {"$top": inputs.get("limit", 20)}
            f = _build_filter(filters)
            if f:
                params["$filter"] = f

            data = await _get(context, "tasks", params)
            items = data.get("value", []) if isinstance(data, dict) else []
            return ActionResult(data={"tasks": items, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@dynamics365.action("create_task")
class CreateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {"subject": inputs["subject"]}
            if inputs.get("description"):
                body["description"] = inputs["description"]
            if inputs.get("due_date"):
                body["scheduledend"] = inputs["due_date"]
            priority_code = TASK_PRIORITY_MAP.get(inputs.get("priority", "Normal"), 1)
            body["prioritycode"] = priority_code

            if inputs.get("regarding_id") and inputs.get("regarding_type"):
                entity_set = REGARDING_TYPE_MAP.get(inputs["regarding_type"].lower())
                if entity_set:
                    body[f"regardingobjectid_{inputs['regarding_type'].lower()}@odata.bind"] = (
                        f"/{entity_set}({inputs['regarding_id']})"
                    )

            data = await _post(context, "tasks", body)
            return ActionResult(data={"task": data or body}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
