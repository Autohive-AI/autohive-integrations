from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Any, Dict

import json
import time
from urllib.parse import quote, urlsplit, urlunsplit

google_looker = Integration.load()

API_VERSION = "4.0"
TOKEN_EXPIRY_SKEW_SECONDS = 60


def _normalize_base_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("base_url must be a non-empty HTTPS URL")

    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("base_url must be an HTTPS origin without credentials, a path, query, or fragment")

    return urlunsplit(("https", parsed.netloc, "", "", ""))


def _path_segment(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return quote(value, safe="")


def _require_object(value: Any, operation: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Looker returned an invalid response for {operation}: expected an object")
    return value


def _require_list(value: Any, operation: str) -> list[Dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Looker returned an invalid response for {operation}: expected an array of objects")
    return value


def _serialize_query_result(value: Any, operation: str) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, str):
        return value
    raise ValueError(f"Looker returned an invalid response for {operation}: expected text or JSON")


def _boolean_param(value: bool) -> str:
    return "true" if value else "false"


class LookerAPIHelper:
    def __init__(
        self,
        context: ExecutionContext,
        base_url: str,
        client_id: str,
        client_secret: str,
    ):
        self.context = context
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = 0.0

    async def _get_access_token(self) -> str:
        if self.access_token and time.monotonic() < self.token_expires_at:
            return self.access_token

        response = await self.context.fetch(
            f"{self.base_url}/api/{API_VERSION}/login",
            method="POST",
            data={"client_id": self.client_id, "client_secret": self.client_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        token_data = _require_object(response.data, "login")
        self.access_token = token_data.get("access_token")
        if not isinstance(self.access_token, str) or not self.access_token:
            raise ValueError("Looker login response did not include a valid access_token")

        expires_in = token_data.get("expires_in", 3600)
        if isinstance(expires_in, bool):
            raise ValueError("Looker login response included an invalid expires_in value")
        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise ValueError("Looker login response included an invalid expires_in value") from exc
        if expires_in <= 0:
            raise ValueError("Looker login response included an invalid expires_in value")
        self.token_expires_at = time.monotonic() + max(0, expires_in - TOKEN_EXPIRY_SKEW_SECONDS)
        return self.access_token

    async def _get_headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {"Authorization": f"token {token}"}

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/api/{API_VERSION}{endpoint}"
        headers = await self._get_headers()
        request_method = method.upper()
        response = await self.context.fetch(
            url,
            method=request_method,
            json=data if request_method in {"POST", "PUT", "PATCH"} else None,
            params=params or None,
            headers=headers,
        )
        return response.data


def build_looker_helper(context: ExecutionContext) -> LookerAPIHelper:
    if not (hasattr(context, "auth") and context.auth):
        raise ValueError("No authentication credentials provided in context")

    credentials = context.auth.get("credentials", {})
    base_url = credentials.get("base_url")
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not all([base_url, client_id, client_secret]):
        missing = [
            k
            for k, v in {"base_url": base_url, "client_id": client_id, "client_secret": client_secret}.items()
            if not v
        ]  # noqa: E501
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    base_url = _normalize_base_url(base_url)
    return LookerAPIHelper(context, base_url, client_id, client_secret)


@google_looker.action("list_dashboards")
class ListDashboards(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)

            params = {}
            if inputs.get("fields") is not None:
                params["fields"] = inputs.get("fields")
            dashboards = _require_list(
                await helper.make_request("GET", "/dashboards", params=params),
                "list dashboards",
            )

            return ActionResult(data={"dashboards": dashboards}, cost_usd=0)

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("get_dashboard")
class GetDashboard(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            dashboard_id = _path_segment(inputs["dashboard_id"], "dashboard_id")

            params = {}
            if inputs.get("fields") is not None:
                params["fields"] = inputs.get("fields")

            dashboard = _require_object(
                await helper.make_request("GET", f"/dashboards/{dashboard_id}", params=params),
                "get dashboard",
            )

            return ActionResult(data={"dashboard": dashboard}, cost_usd=0)

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("execute_lookml_query")
class ExecuteLookMLQuery(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)

            query_data = {"model": inputs["model"], "view": inputs["explore"]}

            fields = (inputs.get("dimensions") or []) + (inputs.get("measures") or [])
            if fields:
                query_data["fields"] = fields
            if inputs.get("filters") is not None:
                query_data["filters"] = inputs.get("filters")
            if inputs.get("sorts") is not None:
                query_data["sorts"] = inputs.get("sorts")
            if inputs.get("limit") is not None:
                query_data["limit"] = str(inputs.get("limit"))

            result_format = inputs.get("result_format", "json")
            params = {}
            if inputs.get("apply_formatting") is not None:
                params["apply_formatting"] = _boolean_param(inputs["apply_formatting"])
            if inputs.get("apply_vis") is not None:
                params["apply_vis"] = _boolean_param(inputs["apply_vis"])

            results = await helper.make_request(
                "POST",
                f"/queries/run/{_path_segment(result_format, 'result_format')}",
                data=query_data,
                params=params,
            )

            return ActionResult(
                data={
                    "query_results": _serialize_query_result(results, "execute LookML query"),
                },
                cost_usd=0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("list_models")
class ListModels(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)

            params = {}
            if inputs.get("fields") is not None:
                params["fields"] = inputs.get("fields")
            if inputs.get("limit") is not None:
                params["limit"] = inputs["limit"]
            if inputs.get("offset") is not None:
                params["offset"] = inputs["offset"]
            if inputs.get("exclude_empty") is not None:
                params["exclude_empty"] = _boolean_param(inputs["exclude_empty"])
            if inputs.get("exclude_hidden") is not None:
                params["exclude_hidden"] = _boolean_param(inputs["exclude_hidden"])
            if inputs.get("include_internal") is not None:
                params["include_internal"] = _boolean_param(inputs["include_internal"])
            if inputs.get("include_self_service") is not None:
                params["include_self_service"] = _boolean_param(inputs["include_self_service"])

            models = _require_list(
                await helper.make_request("GET", "/lookml_models", params=params),
                "list LookML models",
            )

            return ActionResult(data={"models": models}, cost_usd=0)

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("get_model")
class GetModel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            model_name = _path_segment(inputs["model_name"], "model_name")

            params = {}
            if inputs.get("fields") is not None:
                params["fields"] = inputs.get("fields")

            model = _require_object(
                await helper.make_request("GET", f"/lookml_models/{model_name}", params=params),
                "get LookML model",
            )

            return ActionResult(data={"model": model}, cost_usd=0)

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("execute_sql_query")
class ExecuteSQLQuery(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)

            sql_query_data = {"sql": inputs["sql"]}

            connection_name = inputs.get("connection_name")
            model_name = inputs.get("model_name")
            if bool(connection_name) == bool(model_name):
                raise ValueError("Provide exactly one of 'connection_name' or 'model_name'")
            if connection_name:
                sql_query_data["connection_name"] = connection_name
            else:
                sql_query_data["model_name"] = model_name

            if inputs.get("vis_config") is not None:
                sql_query_data["vis_config"] = inputs.get("vis_config")

            sql_query = _require_object(
                await helper.make_request("POST", "/sql_queries", data=sql_query_data),
                "create SQL Runner query",
            )

            slug = sql_query.get("slug")
            if not isinstance(slug, str) or not slug:
                raise ValueError("Looker SQL query response did not include a valid slug")

            result_format = inputs.get("result_format", "json")
            params = {}
            if inputs.get("download") is not None:
                params["download"] = inputs.get("download")

            results = await helper.make_request(
                "POST",
                f"/sql_queries/{_path_segment(slug, 'slug')}/run/{_path_segment(result_format, 'result_format')}",
                params=params,
            )

            return ActionResult(
                data={
                    "slug": slug,
                    "query_results": _serialize_query_result(results, "execute SQL Runner query"),
                },
                cost_usd=0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@google_looker.action("list_connections")
class ListConnections(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)

            params = {}
            if inputs.get("fields") is not None:
                params["fields"] = inputs.get("fields")

            connections = _require_list(
                await helper.make_request("GET", "/connections", params=params),
                "list connections",
            )

            return ActionResult(data={"connections": connections}, cost_usd=0)

        except Exception as e:
            return ActionError(message=str(e))
