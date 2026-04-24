import re
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Any, Dict
import os

_SF_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}([a-zA-Z0-9]{3})?$")


def _validate_sf_id(value: str, name: str) -> str:
    """Raise ValueError if value is not a valid 15- or 18-character Salesforce ID."""
    if not _SF_ID_RE.match(value):
        raise ValueError(f"Invalid Salesforce ID for {name!r}: must be 15 or 18 alphanumeric characters")
    return value


salesforce = Integration.load()

API_VERSION = "v62.0"


def _base_url(instance_url: str) -> str:
    return f"{instance_url.rstrip('/')}/services/data/{API_VERSION}"


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_token_and_instance(context: ExecutionContext):
    credentials = context.auth.get("credentials", {})
    token = credentials.get("access_token", "")
    instance_url = (
        credentials.get("instance_url")
        or context.metadata.get("instance_url")
        or os.environ.get("SALESFORCE_INSTANCE_URL", "")
    )
    if not instance_url:
        raise ValueError("Salesforce instance_url not found in credentials or metadata. Please reconnect.")
    return token, instance_url


@salesforce.action("search_records")
class SearchRecordsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            response = await context.fetch(
                f"{_base_url(instance_url)}/query",
                method="GET",
                headers=_headers(token),
                params={"q": inputs["soql"]},
            )
            return ActionResult(
                data={
                    "result": True,
                    "records": response.data.get("records", []),
                    "total_size": response.data.get("totalSize", 0),
                    "done": response.data.get("done", True),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@salesforce.action("get_record")
class GetRecordAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            object_type = inputs["object_type"]
            record_id = _validate_sf_id(inputs["record_id"], "record_id")
            url = f"{_base_url(instance_url)}/sobjects/{object_type}/{record_id}"

            params = {}
            if inputs.get("fields"):
                params["fields"] = inputs["fields"]

            response = await context.fetch(url, method="GET", headers=_headers(token), params=params)
            return ActionResult(data={"result": True, "record": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@salesforce.action("update_record")
class UpdateRecordAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            object_type = inputs["object_type"]
            record_id = _validate_sf_id(inputs["record_id"], "record_id")
            url = f"{_base_url(instance_url)}/sobjects/{object_type}/{record_id}"

            await context.fetch(url, method="PATCH", headers=_headers(token), json=inputs["fields"])
            return ActionResult(
                data={
                    "result": True,
                    "record_id": record_id,
                    "object_type": object_type,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


def _build_task_query(  # nosec B608
    status=None,
    assigned_to_id=None,
    due_date_from=None,
    due_date_to=None,
    limit=25,
) -> str:
    limit = min(int(limit), 200)
    conditions = []
    if status:
        safe_status = status.replace("'", "\\'")
        conditions.append(f"Status = '{safe_status}'")
    if assigned_to_id:
        conditions.append(f"OwnerId = '{assigned_to_id}'")
    if due_date_from:
        conditions.append(f"ActivityDate >= {due_date_from}")
    if due_date_to:
        conditions.append(f"ActivityDate <= {due_date_to}")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    fields = (
        "Id, Subject, Status, Priority, ActivityDate, Description, "
        "OwnerId, WhoId, WhatId, CreatedDate, LastModifiedDate"
    )
    return f"SELECT {fields} FROM Task{where} ORDER BY ActivityDate DESC LIMIT {limit}"  # nosec B608


def _build_event_query(  # nosec B608
    start_date_from=None,
    start_date_to=None,
    assigned_to_id=None,
    limit=25,
) -> str:
    limit = min(int(limit), 200)
    conditions = []
    if start_date_from:
        conditions.append(f"StartDateTime >= {start_date_from}T00:00:00Z")
    if start_date_to:
        conditions.append(f"StartDateTime <= {start_date_to}T23:59:59Z")
    if assigned_to_id:
        conditions.append(f"OwnerId = '{assigned_to_id}'")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    fields = (
        "Id, Subject, StartDateTime, EndDateTime, Location, Description, "
        "OwnerId, WhoId, WhatId, IsAllDayEvent, CreatedDate"
    )
    return f"SELECT {fields} FROM Event{where} ORDER BY StartDateTime DESC LIMIT {limit}"  # nosec B608


@salesforce.action("list_tasks")
class ListTasksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            soql = _build_task_query(
                status=inputs.get("status"),
                assigned_to_id=inputs.get("assigned_to_id"),
                due_date_from=inputs.get("due_date_from"),
                due_date_to=inputs.get("due_date_to"),
                limit=inputs.get("limit", 25),
            )
            response = await context.fetch(
                f"{_base_url(instance_url)}/query",
                method="GET",
                headers=_headers(token),
                params={"q": soql},
            )
            return ActionResult(
                data={
                    "result": True,
                    "tasks": response.data.get("records", []),
                    "total_size": response.data.get("totalSize", 0),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@salesforce.action("list_events")
class ListEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            soql = _build_event_query(
                start_date_from=inputs.get("start_date_from"),
                start_date_to=inputs.get("start_date_to"),
                assigned_to_id=inputs.get("assigned_to_id"),
                limit=inputs.get("limit", 25),
            )
            response = await context.fetch(
                f"{_base_url(instance_url)}/query",
                method="GET",
                headers=_headers(token),
                params={"q": soql},
            )
            return ActionResult(
                data={
                    "result": True,
                    "events": response.data.get("records", []),
                    "total_size": response.data.get("totalSize", 0),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


def _summarise_task(task: Dict[str, Any]) -> str:
    subject = task.get("Subject") or "No subject"
    status = task.get("Status") or "Unknown"
    priority = task.get("Priority") or "Normal"
    due = task.get("ActivityDate") or "No due date"
    description = task.get("Description") or "No description"
    return f"Task: {subject}\nStatus: {status} | Priority: {priority} | Due: {due}\nDescription: {description}"


def _summarise_event(event: Dict[str, Any]) -> str:
    subject = event.get("Subject") or "No subject"
    start = event.get("StartDateTime") or "Unknown start"
    end = event.get("EndDateTime") or "Unknown end"
    location = event.get("Location") or "No location"
    description = event.get("Description") or "No description"
    all_day = " (All day)" if event.get("IsAllDayEvent") else ""
    return f"Event: {subject}{all_day}\nStart: {start} | End: {end} | Location: {location}\nDescription: {description}"


@salesforce.action("get_task_summary")
class GetTaskSummaryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            task_id = _validate_sf_id(inputs["task_id"], "task_id")
            fields = (
                "Id, Subject, Status, Priority, ActivityDate, Description, "
                "OwnerId, WhoId, WhatId, CreatedDate, LastModifiedDate"
            )
            soql = f"SELECT {fields} FROM Task WHERE Id = '{task_id}' LIMIT 1"  # nosec B608
            response = await context.fetch(
                f"{_base_url(instance_url)}/query",
                method="GET",
                headers=_headers(token),
                params={"q": soql},
            )
            records = response.data.get("records", [])
            if not records:
                return ActionResult(data={"result": False, "error": "Task not found"}, cost_usd=0.0)
            task = records[0]
            return ActionResult(
                data={"result": True, "summary": _summarise_task(task), "task": task},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@salesforce.action("get_event_summary")
class GetEventSummaryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            token, instance_url = _get_token_and_instance(context)
            event_id = _validate_sf_id(inputs["event_id"], "event_id")
            fields = (
                "Id, Subject, StartDateTime, EndDateTime, Location, Description, "
                "OwnerId, WhoId, WhatId, IsAllDayEvent, CreatedDate"
            )
            soql = f"SELECT {fields} FROM Event WHERE Id = '{event_id}' LIMIT 1"  # nosec B608
            response = await context.fetch(
                f"{_base_url(instance_url)}/query",
                method="GET",
                headers=_headers(token),
                params={"q": soql},
            )
            records = response.data.get("records", [])
            if not records:
                return ActionResult(data={"result": False, "error": "Event not found"}, cost_usd=0.0)
            event = records[0]
            return ActionResult(
                data={
                    "result": True,
                    "summary": _summarise_event(event),
                    "event": event,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
