from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any

# Create the integration using the config.json
api_call = Integration.load()

# ---- Action Handlers ----


@api_call.action("get_request")
class GetRequest(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            url = inputs["url"]
            headers = inputs.get("headers", {})
            params = inputs.get("params", {})

            # Make the GET request
            response = await context.fetch(url=url, method="GET", headers=headers, params=params)

            # Try to get response headers if available
            response_headers = {}
            if hasattr(response, "headers"):
                response_headers = dict(response.headers)

            # Return success response
            return ActionResult(
                data={
                    "status_code": getattr(response, "status_code", 200),
                    "response_data": response,
                    "headers": response_headers,
                    "success": True,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "status_code": getattr(e, "status_code", 500),
                    "response_data": None,
                    "headers": {},
                    "success": False,
                    "error": str(e),
                },
                cost_usd=None,
            )


@api_call.action("post_request")
class PostRequest(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            url = inputs["url"]
            headers = inputs.get("headers", {})
            params = inputs.get("params", {})

            # Handle request body - priority: json_body > body
            request_data = None
            if "json_body" in inputs and inputs["json_body"] is not None:
                request_data = inputs["json_body"]
                # Ensure Content-Type is set for JSON
                if "Content-Type" not in headers and "content-type" not in headers:
                    headers["Content-Type"] = "application/json"
            elif "body" in inputs and inputs["body"] is not None:
                request_data = inputs["body"]

            # Make the POST request
            response = await context.fetch(
                url=url,
                method="POST",
                headers=headers,
                params=params,
                json=request_data if "json_body" in inputs else None,
                data=request_data if "json_body" not in inputs else None,
            )

            # Try to get response headers if available
            response_headers = {}
            if hasattr(response, "headers"):
                response_headers = dict(response.headers)

            # Return success response
            return ActionResult(
                data={
                    "status_code": getattr(response, "status_code", 200),
                    "response_data": response,
                    "headers": response_headers,
                    "success": True,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "status_code": getattr(e, "status_code", 500),
                    "response_data": None,
                    "headers": {},
                    "success": False,
                    "error": str(e),
                },
                cost_usd=None,
            )
