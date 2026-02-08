"""
Humanitix Tags action - Retrieve tag information.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import HUMANITIX_API_BASE, get_api_headers, _build_tag_response


@humanitix.action("get_tags")
class GetTagsAction(ActionHandler):
    """
    Retrieve tags from your Humanitix account.

    Tags are used to categorize and filter events in collection pages,
    widgets, or when passed as additional data via API.

    When tag_id is provided, calls GET /tags/{tagId} directly.
    The page_size and page parameters are ignored.

    When tag_id is omitted, calls GET /tags with optional query
    parameters for pagination.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        tag_id = inputs.get("tag_id")

        headers = get_api_headers(context)

        if tag_id:
            url = f"{HUMANITIX_API_BASE}/tags/{tag_id}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            tag_data = response if isinstance(response, dict) else {}
            tags = [_build_tag_response(tag_data)]
        else:
            page_size = inputs.get("page_size")
            page = inputs.get("page", 1)

            params = {"page": page}

            if page_size is not None:
                params["pageSize"] = page_size

            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{HUMANITIX_API_BASE}/tags?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            tags_data = response if isinstance(response, list) else response.get("tags", [])
            tags = [_build_tag_response(t) for t in tags_data]

        return ActionResult(data={"tags": tags})
