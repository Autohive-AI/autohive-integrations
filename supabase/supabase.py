from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any

supabase = Integration.load()


def get_headers(context: ExecutionContext) -> Dict[str, str]:
    service_role_secret = context.auth.get("service_role_secret", "")
    return {
        "apikey": service_role_secret,
        "Authorization": f"Bearer {service_role_secret}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_base_url(context: ExecutionContext) -> str:
    return context.auth.get("host", "").rstrip("/")


# ---- Database (PostgREST) Handlers ----


@supabase.action("select_records")
class SelectRecordsAction(ActionHandler):
    """Query records from a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]

            params = {}
            if inputs.get("select"):
                params["select"] = inputs["select"]
            if inputs.get("filters"):
                for key, value in inputs["filters"].items():
                    params[key] = value
            if inputs.get("order"):
                params["order"] = inputs["order"]
            if inputs.get("limit") is not None:
                headers["Range-Unit"] = "items"
                offset = inputs.get("offset", 0)
                limit = inputs["limit"]
                headers["Range"] = f"{offset}-{offset + limit - 1}"

            resp = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="GET",
                headers=headers,
                params=params if params else None,
            )

            records = resp.data if isinstance(resp.data, list) else []
            return ActionResult(data={"records": records, "count": len(records)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("insert_records")
class InsertRecordsAction(ActionHandler):
    """Insert records into a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]
            records = inputs["records"]

            if inputs.get("on_conflict"):
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                params = {"on_conflict": inputs["on_conflict"]}
            else:
                headers["Prefer"] = "return=representation"
                params = None

            if inputs.get("return_records") is False:
                prefer = "resolution=merge-duplicates,return=minimal" if inputs.get("on_conflict") else "return=minimal"
                headers["Prefer"] = prefer

            resp = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="POST",
                headers=headers,
                params=params,
                json=records,
            )

            result_records = resp.data if isinstance(resp.data, list) else []
            count = len(result_records) if result_records else len(records)
            return ActionResult(data={"records": result_records, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("update_records")
class UpdateRecordsAction(ActionHandler):
    """Update records in a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]
            data = inputs["data"]
            filters = inputs["filters"]

            params = {key: value for key, value in filters.items()}

            return_minimal = inputs.get("return_records") is False
            if return_minimal:
                headers["Prefer"] = "return=minimal"

            resp = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="PATCH",
                headers=headers,
                params=params,
                json=data,
            )

            result_records = resp.data if isinstance(resp.data, list) else []
            count = 0 if return_minimal else len(result_records)
            return ActionResult(data={"records": result_records, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("delete_records")
class DeleteRecordsAction(ActionHandler):
    """Delete records from a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]
            filters = inputs["filters"]

            params = {key: value for key, value in filters.items()}

            return_minimal = not inputs.get("return_records")
            if inputs.get("return_records"):
                headers["Prefer"] = "return=representation"
            else:
                headers["Prefer"] = "return=minimal"

            resp = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="DELETE",
                headers=headers,
                params=params,
            )

            result_records = resp.data if isinstance(resp.data, list) else []
            count = 0 if return_minimal else len(result_records)
            return ActionResult(data={"records": result_records, "count": count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("call_function")
class CallFunctionAction(ActionHandler):
    """Call a PostgreSQL function (RPC)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            function_name = inputs["function_name"]
            params = inputs.get("params", {})

            resp = await context.fetch(
                f"{base_url}/rest/v1/rpc/{function_name}",
                method="POST",
                headers=headers,
                json=params,
            )
            return ActionResult(data={"data": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Storage Handlers ----


@supabase.action("list_buckets")
class ListBucketsAction(ActionHandler):
    """List all storage buckets."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            resp = await context.fetch(f"{base_url}/storage/v1/bucket", method="GET", headers=headers)
            buckets = resp.data if isinstance(resp.data, list) else []
            return ActionResult(data={"buckets": buckets}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("get_bucket")
class GetBucketAction(ActionHandler):
    """Get details of a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            resp = await context.fetch(
                f"{base_url}/storage/v1/bucket/{inputs['bucket_id']}",
                method="GET",
                headers=headers,
            )
            return ActionResult(data={"bucket": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("create_bucket")
class CreateBucketAction(ActionHandler):
    """Create a new storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)

            body: Dict[str, Any] = {"id": inputs["name"], "name": inputs["name"]}
            if inputs.get("public") is not None:
                body["public"] = inputs["public"]
            if inputs.get("file_size_limit"):
                body["file_size_limit"] = inputs["file_size_limit"]
            if inputs.get("allowed_mime_types"):
                body["allowed_mime_types"] = inputs["allowed_mime_types"]

            resp = await context.fetch(
                f"{base_url}/storage/v1/bucket",
                method="POST",
                headers=headers,
                json=body,
            )
            return ActionResult(data={"bucket": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("delete_bucket")
class DeleteBucketAction(ActionHandler):
    """Delete a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            headers.pop("Content-Type", None)

            await context.fetch(
                f"{base_url}/storage/v1/bucket/{inputs['bucket_id']}",
                method="DELETE",
                headers=headers,
            )
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("list_files")
class ListFilesAction(ActionHandler):
    """List files in a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]

            body: Dict[str, Any] = {
                "prefix": inputs.get("path", ""),
                "limit": inputs.get("limit", 100),
                "offset": inputs.get("offset", 0),
            }
            if inputs.get("search"):
                body["search"] = inputs["search"]

            resp = await context.fetch(
                f"{base_url}/storage/v1/object/list/{bucket_id}",
                method="POST",
                headers=headers,
                json=body,
            )
            files = resp.data if isinstance(resp.data, list) else []
            return ActionResult(data={"files": files}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("delete_files")
class DeleteFilesAction(ActionHandler):
    """Delete files from a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]
            paths = inputs["paths"]

            resp = await context.fetch(
                f"{base_url}/storage/v1/object/{bucket_id}",
                method="DELETE",
                headers=headers,
                json={"prefixes": paths},
            )

            if isinstance(resp.data, dict) and resp.data.get("error"):
                return ActionError(message=resp.data.get("message", resp.data["error"]))

            deleted = resp.data if isinstance(resp.data, list) else []
            return ActionResult(data={"deleted": deleted}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("get_public_url")
class GetPublicUrlAction(ActionHandler):
    """Get the public URL for a file."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            bucket_id = inputs["bucket_id"]
            path = inputs["path"]
            public_url = f"{base_url}/storage/v1/object/public/{bucket_id}/{path}"
            return ActionResult(data={"public_url": public_url}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Auth Admin Handlers ----


@supabase.action("list_users")
class ListUsersAction(ActionHandler):
    """List all authenticated users."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)

            params = {}
            if inputs.get("page"):
                params["page"] = inputs["page"]
            if inputs.get("per_page"):
                params["per_page"] = inputs["per_page"]

            resp = await context.fetch(
                f"{base_url}/auth/v1/admin/users",
                method="GET",
                headers=headers,
                params=params if params else None,
            )

            data = resp.data if isinstance(resp.data, dict) else {}
            users = data.get("users", [])
            total = data.get("total", len(users))
            return ActionResult(data={"users": users, "total": total}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("get_user")
class GetUserAction(ActionHandler):
    """Get a user by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            resp = await context.fetch(
                f"{base_url}/auth/v1/admin/users/{inputs['user_id']}",
                method="GET",
                headers=headers,
            )
            return ActionResult(data={"user": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@supabase.action("delete_user")
class DeleteUserAction(ActionHandler):
    """Delete a user by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            headers.pop("Content-Type", None)

            await context.fetch(
                f"{base_url}/auth/v1/admin/users/{inputs['user_id']}",
                method="DELETE",
                headers=headers,
            )
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
