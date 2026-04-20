from typing import Any, Dict
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)

workflowmax = Integration.load()

BASE_URL = "https://api.workflowmax.com/v2"


def _get_token(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {})
    return credentials.get("access_token", "")


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _build_params(**kwargs) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


@workflowmax.action("list_clients")
class ListClientsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                page=inputs.get("page"),
                pageSize=inputs.get("page_size"),
            )
            response = await context.fetch(
                f"{BASE_URL}/clients",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(
                data={"result": True, "clients": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("get_client")
class GetClientAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            uuid = inputs["uuid"]
            response = await context.fetch(
                f"{BASE_URL}/clients/{uuid}",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(data={"result": True, "client": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_client")
class CreateClientAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                name=inputs.get("name"),
                email=inputs.get("email"),
                phone=inputs.get("phone"),
                address=inputs.get("address"),
                city=inputs.get("city"),
                region=inputs.get("region"),
                country=inputs.get("country"),
                postalCode=inputs.get("postal_code"),
            )
            response = await context.fetch(
                f"{BASE_URL}/clients",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "client": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("update_client")
class UpdateClientAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            uuid = inputs["uuid"]
            body = _build_params(
                name=inputs.get("name"),
                email=inputs.get("email"),
                phone=inputs.get("phone"),
                address=inputs.get("address"),
                city=inputs.get("city"),
                region=inputs.get("region"),
                country=inputs.get("country"),
                postalCode=inputs.get("postal_code"),
            )
            response = await context.fetch(
                f"{BASE_URL}/clients/{uuid}",
                method="PUT",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "client": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Client Contacts
# ---------------------------------------------------------------------------


@workflowmax.action("list_client_contacts")
class ListClientContactsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            client_uuid = inputs["client_uuid"]
            response = await context.fetch(
                f"{BASE_URL}/clients/{client_uuid}/contacts",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(
                data={"result": True, "contacts": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_client_contact")
class CreateClientContactAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            client_uuid = inputs["client_uuid"]
            body = _build_params(
                name=inputs.get("name"),
                email=inputs.get("email"),
                phone=inputs.get("phone"),
                mobile=inputs.get("mobile"),
            )
            response = await context.fetch(
                f"{BASE_URL}/clients/{client_uuid}/contacts",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(
                data={"result": True, "contact": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@workflowmax.action("list_jobs")
class ListJobsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                page=inputs.get("page"),
                pageSize=inputs.get("page_size"),
                lastModified=inputs.get("last_modified"),
            )
            response = await context.fetch(
                f"{BASE_URL}/jobs",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(data={"result": True, "jobs": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("get_job")
class GetJobAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            identifier = inputs["identifier"]
            response = await context.fetch(
                f"{BASE_URL}/jobs/{identifier}",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(data={"result": True, "job": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_job")
class CreateJobAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                name=inputs.get("name"),
                clientUuid=inputs.get("client_uuid"),
                description=inputs.get("description"),
                startDate=inputs.get("start_date"),
                dueDate=inputs.get("due_date"),
                categoryUuid=inputs.get("category_uuid"),
            )
            response = await context.fetch(
                f"{BASE_URL}/jobs",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "job": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("update_job")
class UpdateJobAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            identifier = inputs["identifier"]
            body = _build_params(
                name=inputs.get("name"),
                description=inputs.get("description"),
                startDate=inputs.get("start_date"),
                dueDate=inputs.get("due_date"),
                state=inputs.get("state"),
            )
            response = await context.fetch(
                f"{BASE_URL}/jobs/{identifier}",
                method="PUT",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "job": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


@workflowmax.action("list_timesheets")
class ListTimesheetsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                fromDate=inputs.get("from_date"),
                toDate=inputs.get("to_date"),
                staffUuid=inputs.get("staff_uuid"),
                jobUuid=inputs.get("job_uuid"),
            )
            response = await context.fetch(
                f"{BASE_URL}/timesheets",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(
                data={"result": True, "timesheets": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("add_timesheet")
class AddTimesheetAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                jobUuid=inputs.get("job_uuid"),
                taskUuid=inputs.get("task_uuid"),
                staffUuid=inputs.get("staff_uuid"),
                minutes=inputs.get("minutes"),
                date=inputs.get("date"),
                note=inputs.get("note"),
            )
            response = await context.fetch(
                f"{BASE_URL}/timesheets",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(
                data={"result": True, "timesheet": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@workflowmax.action("list_invoices")
class ListInvoicesAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                fromDate=inputs.get("from_date"),
                toDate=inputs.get("to_date"),
                clientUuid=inputs.get("client_uuid"),
                status=inputs.get("status"),
            )
            response = await context.fetch(
                f"{BASE_URL}/invoices",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(
                data={"result": True, "invoices": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("get_invoice")
class GetInvoiceAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            uuid = inputs["uuid"]
            response = await context.fetch(
                f"{BASE_URL}/invoices/{uuid}",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(
                data={"result": True, "invoice": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_invoice")
class CreateInvoiceAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                clientUuid=inputs.get("client_uuid"),
                jobUuid=inputs.get("job_uuid"),
                date=inputs.get("date"),
                dueDate=inputs.get("due_date"),
                description=inputs.get("description"),
                amount=inputs.get("amount"),
            )
            response = await context.fetch(
                f"{BASE_URL}/invoices",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(
                data={"result": True, "invoice": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@workflowmax.action("list_quotes")
class ListQuotesAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                fromDate=inputs.get("from_date"),
                toDate=inputs.get("to_date"),
                clientUuid=inputs.get("client_uuid"),
            )
            response = await context.fetch(
                f"{BASE_URL}/quotes",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(data={"result": True, "quotes": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_quote")
class CreateQuoteAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                jobUuid=inputs.get("job_uuid"),
                date=inputs.get("date"),
                expiryDate=inputs.get("expiry_date"),
                description=inputs.get("description"),
                amount=inputs.get("amount"),
            )
            response = await context.fetch(
                f"{BASE_URL}/quotes",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "quote": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@workflowmax.action("list_tasks")
class ListTasksAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(jobUuid=inputs.get("job_uuid"))
            response = await context.fetch(
                f"{BASE_URL}/tasks",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(data={"result": True, "tasks": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_task")
class CreateTaskAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                name=inputs.get("name"),
                jobUuid=inputs.get("job_uuid"),
                description=inputs.get("description"),
                estimatedMinutes=inputs.get("estimated_minutes"),
                startDate=inputs.get("start_date"),
                dueDate=inputs.get("due_date"),
            )
            response = await context.fetch(
                f"{BASE_URL}/tasks",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "task": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("update_task")
class UpdateTaskAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            uuid = inputs["uuid"]
            body = _build_params(
                name=inputs.get("name"),
                description=inputs.get("description"),
                estimatedMinutes=inputs.get("estimated_minutes"),
                dueDate=inputs.get("due_date"),
                completed=inputs.get("completed"),
            )
            response = await context.fetch(
                f"{BASE_URL}/tasks/{uuid}",
                method="PUT",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "task": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------


@workflowmax.action("list_staff")
class ListStaffAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            response = await context.fetch(
                f"{BASE_URL}/staff",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(data={"result": True, "staff": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("get_staff")
class GetStaffAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            uuid = inputs["uuid"]
            response = await context.fetch(
                f"{BASE_URL}/staff/{uuid}",
                method="GET",
                headers=_headers(token),
            )
            return ActionResult(
                data={"result": True, "staff_member": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------


@workflowmax.action("list_leads")
class ListLeadsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                page=inputs.get("page"),
                pageSize=inputs.get("page_size"),
            )
            response = await context.fetch(
                f"{BASE_URL}/leads",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(data={"result": True, "leads": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_lead")
class CreateLeadAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                name=inputs.get("name"),
                clientUuid=inputs.get("client_uuid"),
                contactName=inputs.get("contact_name"),
                email=inputs.get("email"),
                phone=inputs.get("phone"),
                description=inputs.get("description"),
            )
            response = await context.fetch(
                f"{BASE_URL}/leads",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "lead": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------


@workflowmax.action("list_costs")
class ListCostsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(jobUuid=inputs.get("job_uuid"))
            response = await context.fetch(
                f"{BASE_URL}/costs",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(data={"result": True, "costs": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_cost")
class CreateCostAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                jobUuid=inputs.get("job_uuid"),
                description=inputs.get("description"),
                quantity=inputs.get("quantity"),
                unitCost=inputs.get("unit_cost"),
                unitPrice=inputs.get("unit_price"),
                supplierUuid=inputs.get("supplier_uuid"),
                date=inputs.get("date"),
            )
            response = await context.fetch(
                f"{BASE_URL}/costs",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(data={"result": True, "cost": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------


@workflowmax.action("list_purchase_orders")
class ListPurchaseOrdersAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            params = _build_params(
                fromDate=inputs.get("from_date"),
                toDate=inputs.get("to_date"),
                supplierUuid=inputs.get("supplier_uuid"),
            )
            response = await context.fetch(
                f"{BASE_URL}/purchase-orders",
                method="GET",
                headers=_headers(token),
                params=params,
            )
            return ActionResult(
                data={"result": True, "purchase_orders": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@workflowmax.action("create_purchase_order")
class CreatePurchaseOrderAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        try:
            token = _get_token(context)
            body = _build_params(
                supplierUuid=inputs.get("supplier_uuid"),
                jobUuid=inputs.get("job_uuid"),
                date=inputs.get("date"),
                deliveryDate=inputs.get("delivery_date"),
                description=inputs.get("description"),
                amount=inputs.get("amount"),
            )
            response = await context.fetch(
                f"{BASE_URL}/purchase-orders",
                method="POST",
                headers=_headers(token),
                json=body,
            )
            return ActionResult(
                data={"result": True, "purchase_order": response}, cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
