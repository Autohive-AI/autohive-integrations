"""Perplexity Integration for Autohive

This integration provides web search capabilities using Perplexity's Search API.
"""

import os
from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any

# Load the integration from config.json
perplexity = Integration.load()


async def parse_response(response):
    """Parse the response from context.fetch()"""
    if hasattr(response, "json"):
        return await response.json()
    return response


@perplexity.action("search_web")
class SearchWebActionHandler(ActionHandler):
    """
    Action handler to search the web using Perplexity's Search API.

    Returns ranked, structured search results with titles, URLs, snippets,
    publication dates, and last updated dates.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the search_web action.

        :param inputs: Dictionary with keys:
            - query: Search query (string or array of strings, max 5)
            - max_results: Maximum results to return (1-20, default 10)
            - max_tokens_per_page: Tokens per page (default 1024)
            - country: ISO country code (optional)
        :param context: Execution context with authentication details
        :return: Dictionary with search results
        """

        try:
            api_key = os.environ.get("PERPLEXITY_API_KEY", "")
            if not api_key:
                return ActionResult(
                    data={
                        "results": [],
                        "total_results": 0,
                        "error": "PERPLEXITY_API_KEY environment variable is not set or empty.",
                    }
                )

            query = inputs["query"]

            # Build the request payload
            payload = {"query": query}

            # Add optional parameters if provided
            if "max_results" in inputs:
                payload["max_results"] = inputs["max_results"]

            # Convert content_depth from string enum to max_tokens_per_page integer
            if "content_depth" in inputs:
                token_mapping = {"quick": 512, "default": 2048, "detailed": 8192}
                content_depth_value = inputs["content_depth"]
                payload["max_tokens_per_page"] = token_mapping.get(content_depth_value, 2048)

            if "country" in inputs and inputs["country"]:
                payload["country"] = inputs["country"]

            # Make the API request using context.fetch()
            response = await context.fetch(
                "https://api.perplexity.ai/search",
                method="POST",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )

            # Parse the response
            result = await parse_response(response)

            # Enhance the response with total_results count
            if "results" in result:
                result["total_results"] = len(result["results"])

            return ActionResult(data=result, cost_usd=0.005)

        except KeyError as e:
            return ActionResult(
                data={"results": [], "total_results": 0, "error": f"Missing required input field: {str(e)}"}
            )

        except Exception as e:
            error_message = str(e)

            if "429" in error_message or "rate limit" in error_message.lower():
                return ActionResult(
                    data={
                        "results": [],
                        "total_results": 0,
                        "error": "Rate limit exceeded. Please wait a moment and try again. Perplexity allows 3 requests per second.",  # noqa: E501
                    }
                )
            elif "401" in error_message or "unauthorized" in error_message.lower():
                return ActionResult(
                    data={
                        "results": [],
                        "total_results": 0,
                        "error": "Invalid API key. Please check your PERPLEXITY_API_KEY environment variable.",
                    }
                )
            elif "403" in error_message or "forbidden" in error_message.lower():
                return ActionResult(
                    data={
                        "results": [],
                        "total_results": 0,
                        "error": "Access forbidden. Please ensure you have purchased API credits at https://www.perplexity.ai/settings/api",  # noqa: E501
                    }
                )
            else:
                return ActionResult(
                    data={"results": [], "total_results": 0, "error": f"Failed to search: {error_message}"}
                )
