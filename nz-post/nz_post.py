"""NZ Post lookups using Autohive's server-side application credentials."""

import asyncio
import hashlib
import math
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError
from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)

nz_post = Integration.load(Path(__file__).with_name("config.json"))

TOKEN_URL = "https://oauth.nzpost.co.nz/as/token.oauth2"  # nosec B105
API_BASE_URL = "https://api.nzpost.co.nz"
# Cache only tokens, never parcel or address data. Fingerprints isolate credential rotations.
_token_cache: dict[str, tuple[str, float]] = {}


def _http_error(error: HTTPError, *, token_request: bool = False) -> ActionError:
    """Do not expose provider bodies or exception text, which may contain credentials."""
    if isinstance(error, RateLimitError):
        return ActionError(message=f"NZ Post rate limit reached. Retry after {error.retry_after} seconds.")
    if token_request:
        return ActionError(message="NZ Post application authentication failed. Contact your Autohive administrator.")
    messages = {
        401: "NZ Post authentication failed after renewing the token. Contact your Autohive administrator.",
        403: "NZ Post has not authorised this application for the requested API. Contact your Autohive administrator.",
        404: "NZ Post could not find the requested address.",
        429: "NZ Post rate limit reached. Retry later.",
    }
    return ActionError(
        message=messages.get(error.status, f"NZ Post request failed (HTTP {error.status}). Retry later.")
    )


async def _get_token(context: ExecutionContext) -> str | ActionError:
    client_id = os.environ.get("NZPOST_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NZPOST_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return ActionError(
            message="NZ Post is not configured. An Autohive administrator must set "
            "NZPOST_CLIENT_ID and NZPOST_CLIENT_SECRET."
        )
    cache_key = hashlib.sha256(f"{client_id}\0{client_secret}".encode()).hexdigest()
    cached = _token_cache.get(cache_key)
    if cached and time.monotonic() < cached[1]:
        return cached[0]

    requested_at = time.monotonic()
    try:
        response = await context.fetch(
            TOKEN_URL,
            method="POST",
            content_type="application/x-www-form-urlencoded",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        )
    except HTTPError as error:
        return _http_error(error, token_request=True)
    except (ClientError, asyncio.TimeoutError):
        return ActionError(message="NZ Post authentication service is unavailable. Retry later.")

    body = response.data
    if not isinstance(body, dict) or not isinstance(body.get("access_token"), str) or not body["access_token"].strip():
        return ActionError(message="NZ Post returned an invalid authentication response.")
    if str(body.get("token_type", "Bearer")).lower() != "bearer":
        return ActionError(message="NZ Post returned an unsupported token type.")
    try:
        lifetime = float(body["expires_in"])
    except (KeyError, TypeError, ValueError):
        return ActionError(message="NZ Post returned an invalid token expiry.")
    if not math.isfinite(lifetime) or lifetime <= 0:
        return ActionError(message="NZ Post returned an invalid token expiry.")
    _token_cache.clear()
    _token_cache[cache_key] = (body["access_token"], requested_at + max(0, lifetime - 60))
    return body["access_token"]


async def _request(
    context: ExecutionContext, path: str, params: dict[str, Any] | None = None
) -> dict[str, Any] | ActionError:
    for attempt in range(2):
        token = await _get_token(context)
        if isinstance(token, ActionError):
            return token
        try:
            response = await context.fetch(
                f"{API_BASE_URL}{path}",
                method="GET",
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except HTTPError as error:
            if error.status == 401:
                _token_cache.clear()
                if attempt == 0:
                    continue
            return _http_error(error)
        except (ClientError, asyncio.TimeoutError):
            return ActionError(message="NZ Post is unavailable. Retry later.")
        body = response.data
        if not isinstance(body, dict):
            return ActionError(message="NZ Post returned an invalid response.")
        # NZ Post can return application errors inside HTTP 200 responses.
        errors = body.get("errors") or []
        if isinstance(errors, dict):
            errors = [errors]
        codes = (
            [str(item.get("code", "")) for item in errors if isinstance(item, dict)] if isinstance(errors, list) else []
        )
        hard_errors = [code for code in codes if re.fullmatch(r"[45]\d{5}", code)]
        if body.get("success") is not True or hard_errors:
            suffix = f" (code {hard_errors[0]})" if hard_errors else ""
            return ActionError(
                message=f"NZ Post could not complete this lookup{suffix}. Check the input and API access."
            )
        return body
    raise RuntimeError("NZ Post authentication retry exhausted")


@nz_post.action("search_addresses")
class SearchAddressesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        query = inputs["query"].strip()
        if len(query) < 4:
            return ActionError(message="Enter at least four characters of a New Zealand address.")
        body = await _request(
            context, "/parceladdress/2.0/domestic/addresses", {"q": query, "count": inputs.get("count", 10)}
        )
        if isinstance(body, ActionError):
            return body
        if not isinstance(body.get("addresses"), list):
            return ActionError(message="NZ Post returned an invalid address search response.")
        return ActionResult(data=body)


@nz_post.action("get_address")
class GetAddressAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        address_id = inputs["address_id"].strip()
        if not re.fullmatch(r"[0-9]+", address_id):
            return ActionError(message="Enter a numeric address ID from Search Addresses.")
        body = await _request(context, f"/parceladdress/2.0/domestic/addresses/{quote(address_id, safe='')}")
        if isinstance(body, ActionError):
            return body
        if not isinstance(body.get("address"), dict):
            return ActionError(message="NZ Post returned an invalid address detail response.")
        return ActionResult(data=body)


@nz_post.action("check_address")
class CheckAddressAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        first_line = inputs["address_line_1"].strip()
        if not first_line:
            return ActionError(message="Enter the first line of a New Zealand address.")
        params = {"address_line_1": first_line, "max": inputs.get("count", 10)}
        optional_lines = {
            "address_line_2": inputs.get("address_line_2", ""),
            "address_line_3": inputs.get("address_line_3", ""),
            "address_line_4": inputs.get("address_line_4", ""),
            "address_line_5": inputs.get("address_line_5", ""),
        }
        for field, value in optional_lines.items():
            value = value.strip()
            if value:
                params[field] = value
        body = await _request(context, "/addresschecker/1.0/find", params)
        if isinstance(body, ActionError):
            return body
        if not isinstance(body.get("addresses"), list):
            return ActionError(message="NZ Post returned an invalid address match response.")
        # Preserve all candidates and scores. A match does not establish validity or delivery eligibility.
        return ActionResult(data=body)


@nz_post.action("get_postal_address_details")
class GetPostalAddressDetailsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        dpid = inputs["dpid"].strip()
        if not re.fullmatch(r"[0-9]+", dpid):
            return ActionError(message="Enter a numeric delivery point identifier (DPID).")
        body = await _request(context, "/addresschecker/1.0/details", {"dpid": dpid})
        if isinstance(body, ActionError):
            return body
        if not isinstance(body.get("details"), (list, dict)):
            return ActionError(message="NZ Post returned an invalid postal address detail response.")
        return ActionResult(data=body)


@nz_post.action("search_partial_addresses")
class SearchPartialAddressesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        query = inputs["query"].strip()
        if not query:
            return ActionError(message="Enter part of a New Zealand street, suburb, or town.")
        body = await _request(
            context, "/addresschecker/1.0/suggest_partial", {"q": query, "max": inputs.get("count", 10)}
        )
        if isinstance(body, ActionError):
            return body
        if not isinstance(body.get("addresses"), list):
            return ActionError(message="NZ Post returned an invalid partial address response.")
        return ActionResult(data=body)
