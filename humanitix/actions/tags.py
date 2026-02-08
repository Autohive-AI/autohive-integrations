"""
Humanitix Tags action - Retrieve tag information.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import get_api_headers, build_url, build_error_result, build_paginated_result, fetch_single_resource


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
            return await fetch_single_resource(context, f"tags/{tag_id}", {}, "tag")
        else:
            page_size = inputs.get("page_size")
            page = inputs.get("page", 1)

            params = {"page": page}

            if page_size is not None:
                params["pageSize"] = page_size

            url = build_url("tags", params)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            return build_paginated_result(response, "tags", page, page_size)
