# API Call Integration for Autohive

Generic API integration for making HTTP requests to any API endpoint directly from Autohive workflows.

## Description

The API Call integration provides a flexible way to make GET and POST HTTP requests to any API endpoint. It uses the Autohive SDK's `context.fetch()` method for making requests, supporting custom headers, query parameters, and request bodies. Ideal for connecting to APIs that don't have a dedicated Autohive integration, webhook testing, and custom API workflow automation.

## Setup & Authentication

No authentication configuration is required for this integration. Authentication to target APIs is handled via custom headers (e.g., `Authorization` bearer tokens, API keys) passed as inputs to each action.

## Actions

### Action: `get_request`

*   **Description:** Make a GET request to any API endpoint.
*   **Inputs:**
    *   `url` (string, required): The URL to make the GET request to.
    *   `headers` (object, optional): Headers to include in the request.
    *   `params` (object, optional): Query parameters to include in the request.
*   **Outputs:**
    *   `status_code` (integer): HTTP status code of the response.
    *   `response_data`: The response data from the API call.
    *   `headers` (object): Response headers.
    *   `success` (boolean): Whether the request was successful.
    *   `error` (string): Error message if the request failed.

### Action: `post_request`

*   **Description:** Make a POST request to any API endpoint.
*   **Inputs:**
    *   `url` (string, required): The URL to make the POST request to.
    *   `headers` (object, optional): Headers to include in the request.
    *   `body` (any, optional): Request body data (can be object, string, or array).
    *   `json_body` (object, optional): JSON request body (alternative to body field for JSON data). Automatically sets `Content-Type: application/json`.
    *   `params` (object, optional): Query parameters to include in the request.
*   **Outputs:**
    *   `status_code` (integer): HTTP status code of the response.
    *   `response_data`: The response data from the API call.
    *   `headers` (object): Response headers.
    *   `success` (boolean): Whether the request was successful.
    *   `error` (string): Error message if the request failed.

## Known Limitations

This integration is still pinned to `autohive-integrations-sdk~=1.0.2`. That SDK 1.x contract returns the parsed response body (dict, string, or None), not a `FetchResponse`. As a result, this implementation has these limitations:

*   **`status_code`** — Falls back to `200` on success and `500` on error unless the returned object or exception exposes `status_code`. Do not rely on it as the actual HTTP status.
*   **`headers`** — Successful SDK 1.x calls do not expose response headers; this field is an empty object (`{}`). Error paths also return `{}`.

These are limitations of this shipped integration, not of current SDK 2.x. SDK 2.x returns `FetchResponse` with `.data`, `.status`, and `.headers`, and SDK 2.1.0 also exposes headers on HTTP exceptions. Adopting that contract requires an explicit implementation and dependency upgrade, not just changing the pin; this documentation update does neither.

## Requirements

*   `autohive-integrations-sdk~=1.0.2` (see `requirements.txt`)

## Testing

To run the tests (requires Python 3.13+):

1.  Navigate to the integration's directory: `cd api-call`
2.  Install dependencies: `pip install -r requirements.txt -t dependencies`
3.  Run the tests: `python tests/test_api_call.py`
