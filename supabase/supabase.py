from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

# Create the integration
supabase = Integration.load()


def get_headers(context: ExecutionContext) -> Dict[str, str]:
    """Get the authorization headers for Supabase API requests."""
    credentials = context.auth.get("credentials", {})
    service_role_secret = credentials.get("service_role_secret", "")
    return {
        "apikey": service_role_secret,
        "Authorization": f"Bearer {service_role_secret}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def get_base_url(context: ExecutionContext) -> str:
    """Get the base URL from the host credential."""
    credentials = context.auth.get("credentials", {})
    host = credentials.get("host", "").rstrip("/")
    return host


# ---- Database (PostgREST) Handlers ----

@supabase.action("select_records")
class SelectRecordsAction(ActionHandler):
    """Query records from a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]

            # Build query parameters
            params = {}
            if inputs.get("select"):
                params["select"] = inputs["select"]

            # Add filters
            if inputs.get("filters"):
                for key, value in inputs["filters"].items():
                    params[key] = value

            if inputs.get("order"):
                params["order"] = inputs["order"]

            if inputs.get("limit"):
                headers["Range-Unit"] = "items"
                offset = inputs.get("offset", 0)
                limit = inputs["limit"]
                headers["Range"] = f"{offset}-{offset + limit - 1}"

            response = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="GET",
                headers=headers,
                params=params if params else None
            )

            records = response if isinstance(response, list) else []

            return ActionResult(
                data={"records": records, "count": len(records), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"records": [], "count": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("insert_records")
class InsertRecordsAction(ActionHandler):
    """Insert records into a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]
            records = inputs["records"]

            # Handle upsert
            if inputs.get("on_conflict"):
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                params = {"on_conflict": inputs["on_conflict"]}
            else:
                headers["Prefer"] = "return=representation"
                params = None

            # Determine if we should return records
            if inputs.get("return_records") == False:
                headers["Prefer"] = "return=minimal"

            response = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="POST",
                headers=headers,
                params=params,
                json=records
            )

            result_records = response if isinstance(response, list) else []

            return ActionResult(
                data={"records": result_records, "count": len(result_records), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"records": [], "count": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


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

            # Build filter params
            params = {}
            for key, value in filters.items():
                params[key] = value

            # Determine if we should return records
            if inputs.get("return_records") == False:
                headers["Prefer"] = "return=minimal"

            response = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="PATCH",
                headers=headers,
                params=params,
                json=data
            )

            result_records = response if isinstance(response, list) else []

            return ActionResult(
                data={"records": result_records, "count": len(result_records), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"records": [], "count": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("delete_records")
class DeleteRecordsAction(ActionHandler):
    """Delete records from a table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            table = inputs["table"]
            filters = inputs["filters"]

            # Build filter params
            params = {}
            for key, value in filters.items():
                params[key] = value

            # Determine if we should return records
            if inputs.get("return_records"):
                headers["Prefer"] = "return=representation"
            else:
                headers["Prefer"] = "return=minimal"

            response = await context.fetch(
                f"{base_url}/rest/v1/{table}",
                method="DELETE",
                headers=headers,
                params=params
            )

            result_records = response if isinstance(response, list) else []

            return ActionResult(
                data={"records": result_records, "count": len(result_records), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"records": [], "count": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("call_function")
class CallFunctionAction(ActionHandler):
    """Call a PostgreSQL function (RPC)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            function_name = inputs["function_name"]
            params = inputs.get("params", {})

            response = await context.fetch(
                f"{base_url}/rest/v1/rpc/{function_name}",
                method="POST",
                headers=headers,
                json=params
            )

            return ActionResult(
                data={"data": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"data": None, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Storage Handlers ----

@supabase.action("list_buckets")
class ListBucketsAction(ActionHandler):
    """List all storage buckets."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)

            response = await context.fetch(
                f"{base_url}/storage/v1/bucket",
                method="GET",
                headers=headers
            )

            buckets = response if isinstance(response, list) else []

            return ActionResult(
                data={"buckets": buckets, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"buckets": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("get_bucket")
class GetBucketAction(ActionHandler):
    """Get details of a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]

            response = await context.fetch(
                f"{base_url}/storage/v1/bucket/{bucket_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={"bucket": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bucket": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("create_bucket")
class CreateBucketAction(ActionHandler):
    """Create a new storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)

            body = {
                "id": inputs["name"],
                "name": inputs["name"]
            }

            if "public" in inputs:
                body["public"] = inputs["public"]
            if inputs.get("file_size_limit"):
                body["file_size_limit"] = inputs["file_size_limit"]
            if inputs.get("allowed_mime_types"):
                body["allowed_mime_types"] = inputs["allowed_mime_types"]

            response = await context.fetch(
                f"{base_url}/storage/v1/bucket",
                method="POST",
                headers=headers,
                json=body
            )

            return ActionResult(
                data={"bucket": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bucket": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("delete_bucket")
class DeleteBucketAction(ActionHandler):
    """Delete a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]

            # Remove Content-Type for DELETE without body
            del headers["Content-Type"]

            await context.fetch(
                f"{base_url}/storage/v1/bucket/{bucket_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("list_files")
class ListFilesAction(ActionHandler):
    """List files in a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]

            body = {
                "prefix": inputs.get("path", ""),
                "limit": inputs.get("limit", 100),
                "offset": inputs.get("offset", 0)
            }

            if inputs.get("search"):
                body["search"] = inputs["search"]

            response = await context.fetch(
                f"{base_url}/storage/v1/object/list/{bucket_id}",
                method="POST",
                headers=headers,
                json=body
            )

            files = response if isinstance(response, list) else []

            return ActionResult(
                data={"files": files, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"files": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("delete_files")
class DeleteFilesAction(ActionHandler):
    """Delete files from a storage bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            bucket_id = inputs["bucket_id"]
            paths = inputs["paths"]

            response = await context.fetch(
                f"{base_url}/storage/v1/object/{bucket_id}",
                method="DELETE",
                headers=headers,
                json={"prefixes": paths}
            )

            deleted = response if isinstance(response, list) else []

            return ActionResult(
                data={"deleted": deleted, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("get_public_url")
class GetPublicUrlAction(ActionHandler):
    """Get the public URL for a file."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            bucket_id = inputs["bucket_id"]
            path = inputs["path"]

            public_url = f"{base_url}/storage/v1/object/public/{bucket_id}/{path}"

            return ActionResult(
                data={"public_url": public_url, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"public_url": "", "result": False, "error": str(e)},
                cost_usd=0.0
            )


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

            response = await context.fetch(
                f"{base_url}/auth/v1/admin/users",
                method="GET",
                headers=headers,
                params=params if params else None
            )

            users = response.get("users", []) if isinstance(response, dict) else []
            total = response.get("total", len(users)) if isinstance(response, dict) else len(users)

            return ActionResult(
                data={"users": users, "total": total, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"users": [], "total": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("get_user")
class GetUserAction(ActionHandler):
    """Get a user by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            user_id = inputs["user_id"]

            response = await context.fetch(
                f"{base_url}/auth/v1/admin/users/{user_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={"user": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@supabase.action("delete_user")
class DeleteUserAction(ActionHandler):
    """Delete a user by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_headers(context)
            user_id = inputs["user_id"]

            # Remove Content-Type for DELETE without body
            del headers["Content-Type"]

            await context.fetch(
                f"{base_url}/auth/v1/admin/users/{user_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )
