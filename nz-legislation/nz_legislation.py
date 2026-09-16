"""Read-only integration for the New Zealand Legislation Data API."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote, urlparse

import aiohttp
from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)

nz_legislation = Integration.load()

API_BASE_URL = "https://api.legislation.govt.nz/v0"
OFFICIAL_CONTENT_HOSTS = {"legislation.govt.nz", "www.legislation.govt.nz"}
OFFICIAL_CONTENT_BASE_URL = "https://www.legislation.govt.nz"
DEFAULT_XML_CHUNK_BYTES = 20_000
XML_RANGE_ATTEMPTS = 3
_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
_VERSION_ID = re.compile(r"^[A-Za-z0-9~-]+(?:_[A-Za-z0-9~-]+){5}$")
_UNEXPECTED_ERROR = (
    "The New Zealand Legislation integration hit an unexpected error handling this request. Try again later."
)
_NETWORK_ERROR = "The New Zealand Legislation service could not complete the request. Try again later."
_ACT_FILTERS = {"act_type", "act_classification", "act_status"}
_INSTRUMENT_FILTERS = {"instrument_type_group", "instrument_status", "instrument_classification"}
_BILL_FILTERS = {"bill_type", "bill_status"}
_VERSION_FIELDS = (
    "act_classification",
    "act_status",
    "act_type",
    "bill_status",
    "bill_type",
    "instrument_classification",
    "instrument_status",
    "instrument_type_group",
)


class LegislationError(Exception):
    """An expected integration error whose message is safe to show to users."""


def _api_headers(context: ExecutionContext) -> dict[str, str]:
    auth = context.auth or {}
    credentials = auth.get("credentials", {}) if isinstance(auth, dict) else {}
    api_key = credentials.get("api_key") if isinstance(credentials, dict) else None
    if not isinstance(api_key, str) or not api_key.strip():
        raise LegislationError("A New Zealand Legislation API key is required.")
    return {"Accept": "application/json", "X-Api-Key": api_key.strip()}


def _rate_limit(headers: Any) -> dict[str, int | None]:
    normalised = {str(key).lower(): value for key, value in (headers or {}).items()}

    def parse(name: str) -> int | None:
        value = normalised.get(name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "limit": parse("x-ratelimit-limit"),
        "remaining": parse("x-ratelimit-remaining"),
        "reset_at": parse("x-ratelimit-reset"),
    }


def _formats(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    formats = []
    for item in value:
        if not isinstance(item, dict):
            raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
        format_type, url = item.get("type"), item.get("url")
        if not isinstance(format_type, str) or not isinstance(url, str):
            raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
        formats.append({"type": format_type, "url": url})
    return formats


def _agencies(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(agency, str) for agency in value):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return value


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return value


def _nullable_string(data: dict[str, Any], field: str) -> str | None:
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return value


def _required_int(data: dict[str, Any], field: str, minimum: int) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return value


def _version(data: dict[str, Any]) -> dict[str, Any]:
    result = {
        "title": _required_string(data, "title"),
        "version_id": _required_string(data, "version_id"),
        "work_id": _required_string(data, "work_id"),
        "legislation_status": _nullable_string(data, "legislation_status"),
        "legislation_type": _required_string(data, "legislation_type"),
        "administering_agencies": _agencies(data.get("administering_agencies")),
        "formats": _formats(data.get("formats")),
    }
    for field in _VERSION_FIELDS:
        result[field] = _nullable_string(data, field)
    return result


def _work(data: dict[str, Any]) -> dict[str, Any]:
    matching = data.get("latest_matching_version")
    if not isinstance(matching, dict) or not isinstance(matching.get("is_latest_version"), bool):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    latest_matching_version = {
        "title": _required_string(matching, "title"),
        "version_id": _required_string(matching, "version_id"),
        "is_latest_version": matching["is_latest_version"],
        "formats": _formats(matching.get("formats")),
    }
    result = {
        "work_id": _required_string(data, "work_id"),
        "legislation_status": _nullable_string(data, "legislation_status"),
        "legislation_type": _required_string(data, "legislation_type"),
        "publisher": _nullable_string(data, "publisher"),
        "administering_agencies": _agencies(data.get("administering_agencies")),
        "latest_matching_version": latest_matching_version,
    }
    for field in _VERSION_FIELDS:
        result[field] = _nullable_string(data, field)
    return result


def _object_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return data


def _results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results")
    if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
        raise LegislationError("The New Zealand Legislation API returned an unexpected response.")
    return results


def _validate_search_filters(inputs: dict[str, Any]) -> None:
    legislation_type = inputs.get("legislation_type")
    supplied = set(inputs)
    if supplied & _ACT_FILTERS and legislation_type != "act":
        raise LegislationError("Act filters require legislation_type='act'.")
    if supplied & _INSTRUMENT_FILTERS and legislation_type != "secondary_legislation":
        raise LegislationError("Instrument filters require legislation_type='secondary_legislation'.")
    if supplied & _BILL_FILTERS and legislation_type != "bill":
        raise LegislationError("Bill filters require legislation_type='bill'.")


def _http_error(exc: HTTPError, *, resource: str = "request") -> ActionError:
    if isinstance(exc, RateLimitError):
        return ActionError(
            message=(
                "The New Zealand Legislation API daily API-key quota has been reached. "
                "It resets at midnight New Zealand time; wait until the reset before retrying."
            )
        )
    if exc.status == 400:
        return ActionError(message="The New Zealand Legislation API rejected the request. Check the supplied inputs.")
    if exc.status == 401:
        return ActionError(message="The New Zealand Legislation API rejected the API key. Check the connected account.")
    if exc.status == 403:
        return ActionError(
            message=(
                "The New Zealand Legislation API refused the request. Its per-IP burst limit may have been reached; "
                "wait five minutes before retrying."
            )
        )
    if exc.status == 404:
        return ActionError(message=f"The New Zealand Legislation API could not find the requested {resource}.")
    return ActionError(message=_NETWORK_ERROR)


def _unexpected_error(context: ExecutionContext, action: str, exc: Exception) -> ActionError:
    context.logger.error(
        "Unexpected %s executing New Zealand Legislation action %s",
        type(exc).__name__,
        action,
    )
    return ActionError(message=_UNEXPECTED_ERROR)


def _trusted_xml_url(formats: list[dict[str, str]]) -> str:
    xml_url = next((item["url"] for item in formats if item["type"].lower() == "xml"), None)
    if not xml_url:
        raise LegislationError("This version does not provide an XML format.")
    parsed = urlparse(xml_url)
    try:
        port = parsed.port
    except ValueError:
        raise LegislationError("The API returned an untrusted XML format URL, so it was not fetched.") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in OFFICIAL_CONTENT_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise LegislationError("The API returned an untrusted XML format URL, so it was not fetched.")
    return xml_url


def _canonical_xml_url(version_id: str) -> str:
    if not _VERSION_ID.fullmatch(version_id):
        raise LegislationError("version_id does not follow the documented six-part identifier format.")
    path = "/".join(quote(component, safe="~-") for component in version_id.split("_"))
    return f"{OFFICIAL_CONTENT_BASE_URL}/{path}.xml"


def _retry_after_seconds(headers: Any) -> int:
    try:
        return min(5, max(1, int(headers.get("Retry-After", "2"))))
    except (AttributeError, TypeError, ValueError):
        return 2


def _continued_xml_source(value: Any, version_id: str) -> dict[str, str]:
    source = _object_response(value)
    if _required_string(source, "version_id") != version_id:
        raise LegislationError("The supplied XML source does not match version_id.")
    source_url = _required_string(source, "source_url")
    if source_url != _canonical_xml_url(version_id):
        raise LegislationError("The supplied XML source does not match version_id.")
    return {
        "version_id": version_id,
        "source_url": source_url,
    }


async def _get_version_response(version_id: str, context: ExecutionContext):
    encoded_id = quote(version_id, safe="")
    return await context.fetch(
        f"{API_BASE_URL}/versions/{encoded_id}/",
        method="GET",
        headers=_api_headers(context),
    )


def _decode_xml_range(body: bytes, content_range: str, offset: int, max_bytes: int) -> tuple[str, int, int, int | None]:
    match = _CONTENT_RANGE.fullmatch(content_range)
    if not match:
        raise LegislationError("The New Zealand Legislation website returned an invalid XML byte range.")
    range_start, range_end, total_bytes = (int(value) for value in match.groups())
    if range_start != offset or range_end < range_start or range_end >= total_bytes:
        raise LegislationError("The New Zealand Legislation website returned an invalid XML byte range.")
    if len(body) != range_end - range_start + 1:
        raise LegislationError("The New Zealand Legislation website returned an incomplete XML byte range.")

    returned_bytes = min(max_bytes, len(body))
    while returned_bytes:
        try:
            xml = body[:returned_bytes].decode("utf-8")
            break
        except UnicodeDecodeError as exc:
            if exc.start < returned_bytes - 3:
                raise LegislationError("The legislation XML is not valid UTF-8 at the requested offset.") from None
            returned_bytes -= 1
    else:
        raise LegislationError("The legislation XML is not valid UTF-8 at the requested offset.")

    if offset == 0 and not xml.lstrip("\ufeff \t\r\n").startswith("<?xml"):
        raise LegislationError("The New Zealand Legislation website returned an unexpected XML response.")

    next_offset = offset + returned_bytes
    return xml, returned_bytes, total_bytes, next_offset if next_offset < total_bytes else None


async def _fetch_xml_chunk(source_url: str, offset: int, max_bytes: int) -> tuple[str, int, int, int | None]:
    """Read a bounded UTF-8 byte range without downloading the complete XML document."""
    requested_end = offset + max_bytes + 2
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {
        "Accept": "application/xml",
        "Accept-Encoding": "identity",
        "Range": f"bytes={offset}-{requested_end}",
    }

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(XML_RANGE_ATTEMPTS):
            request_headers = dict(headers)
            if attempt:
                request_headers.update({"Cache-Control": "no-cache", "Pragma": "no-cache"})

            async with session.get(source_url, headers=request_headers, allow_redirects=False, ssl=True) as response:
                if response.status in {200, 202} and attempt < XML_RANGE_ATTEMPTS - 1:
                    response.close()
                    if response.status == 202:
                        await asyncio.sleep(_retry_after_seconds(response.headers))
                    continue
                if response.status == 404:
                    raise LegislationError(
                        "The New Zealand Legislation website could not find the requested XML document."
                    )
                if response.status == 416:
                    raise LegislationError("offset is outside the XML document's byte range.")
                if response.status == 403:
                    raise LegislationError("The New Zealand Legislation website refused the XML document request.")
                if response.status == 429:
                    raise LegislationError("The New Zealand Legislation website temporarily rate-limited XML requests.")
                if response.status >= 500:
                    raise LegislationError("The New Zealand Legislation website could not provide the XML document.")
                if response.status != 206:
                    raise LegislationError(
                        "The New Zealand Legislation website did not return a bounded XML byte range "
                        f"after retrying (HTTP {response.status})."
                    )

                content_type = response.headers.get("Content-Type", "").partition(";")[0].strip().lower()
                if content_type not in {"application/xml", "text/xml"}:
                    raise LegislationError("The New Zealand Legislation website returned an unexpected XML response.")

                body = bytearray()
                async for chunk in response.content.iter_chunked(16_384):
                    body.extend(chunk)
                    if len(body) > max_bytes + 3:
                        raise LegislationError(
                            "The New Zealand Legislation website exceeded the requested XML byte range."
                        )

                return _decode_xml_range(bytes(body), response.headers.get("Content-Range", ""), offset, max_bytes)

    raise LegislationError("The New Zealand Legislation website did not return a bounded XML byte range.")


@nz_legislation.action("search_legislation")
class SearchLegislationAction(ActionHandler):
    """Search legislation works using the official site-search filters."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        page, per_page = inputs.get("page", 1), inputs.get("per_page", 20)
        try:
            _validate_search_filters(inputs)
            optional_params = {
                "search_term": inputs.get("search_term"),
                "search_field": inputs.get("search_field"),
                "legislation_status": inputs.get("legislation_status"),
                "legislation_type": inputs.get("legislation_type"),
                "act_type": inputs.get("act_type"),
                "act_classification": inputs.get("act_classification"),
                "act_status": inputs.get("act_status"),
                "instrument_type_group": inputs.get("instrument_type_group"),
                "instrument_status": inputs.get("instrument_status"),
                "instrument_classification": inputs.get("instrument_classification"),
                "bill_type": inputs.get("bill_type"),
                "bill_status": inputs.get("bill_status"),
                "administering_agencies": inputs.get("administering_agencies"),
                "sort_by": inputs.get("sort_by"),
                "publisher": inputs.get("publisher"),
            }
            params = {key: value for key, value in optional_params.items() if value is not None}
            params.update({"page": page, "per_page": per_page})
            response = await context.fetch(
                f"{API_BASE_URL}/works/",
                method="GET",
                headers=_api_headers(context),
                params=params,
            )
            data = _object_response(response.data)
            total = _required_int(data, "total", 0)
            response_page = _required_int(data, "page", 1)
            response_per_page = _required_int(data, "per_page", 1)
            if response_page != page or response_per_page != per_page:
                raise LegislationError("The New Zealand Legislation API did not honour the requested search page.")
            return ActionResult(
                data={
                    "works": [_work(item) for item in _results(data)],
                    "page": response_page,
                    "per_page": response_per_page,
                    "total": total,
                    "has_next_page": response_page * response_per_page < total,
                    "rate_limit": _rate_limit(response.headers),
                }
            )
        except LegislationError as exc:
            return ActionError(message=str(exc))
        except HTTPError as exc:
            return _http_error(exc)
        except (aiohttp.ClientError, TimeoutError):
            return ActionError(message=_NETWORK_ERROR)
        except Exception as exc:
            return _unexpected_error(context, "search_legislation", exc)


@nz_legislation.action("list_versions")
class ListVersionsAction(ActionHandler):
    """List one page of versions advertised for a legislation work."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        work_id = inputs["work_id"]
        page, per_page = inputs.get("page", 1), inputs.get("per_page", 20)
        try:
            response = await context.fetch(
                f"{API_BASE_URL}/works/{quote(work_id, safe='')}/versions/",
                method="GET",
                headers=_api_headers(context),
                params={"sort": inputs.get("sort", "desc"), "page": page, "per_page": per_page},
            )
            data = _object_response(response.data)
            versions = [_version(item) for item in _results(data)]
            total = _required_int(data, "total", 0)
            response_page = _required_int(data, "page", 1)
            response_per_page = _required_int(data, "per_page", 1)
            # The v0 OpenAPI document omits these request parameters even though
            # its response is paginated and the live endpoint supports both.
            if response_page != page or response_per_page != per_page:
                raise LegislationError("The New Zealand Legislation API did not honour the requested version page.")
            return ActionResult(
                data={
                    "work_id": work_id,
                    "versions": versions,
                    "page": response_page,
                    "per_page": response_per_page,
                    "count": len(versions),
                    "total": total,
                    "has_next_page": response_page * response_per_page < total,
                    "rate_limit": _rate_limit(response.headers),
                }
            )
        except LegislationError as exc:
            return ActionError(message=str(exc))
        except HTTPError as exc:
            return _http_error(exc, resource="work")
        except (aiohttp.ClientError, TimeoutError):
            return ActionError(message=_NETWORK_ERROR)
        except Exception as exc:
            return _unexpected_error(context, "list_versions", exc)


@nz_legislation.action("get_version")
class GetVersionAction(ActionHandler):
    """Get metadata and available formats for one legislation version."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        try:
            response = await _get_version_response(inputs["version_id"], context)
            return ActionResult(
                data={
                    "version": _version(_object_response(response.data)),
                    "rate_limit": _rate_limit(response.headers),
                }
            )
        except LegislationError as exc:
            return ActionError(message=str(exc))
        except HTTPError as exc:
            return _http_error(exc, resource="version")
        except (aiohttp.ClientError, TimeoutError):
            return ActionError(message=_NETWORK_ERROR)
        except Exception as exc:
            return _unexpected_error(context, "get_version", exc)


@nz_legislation.action("get_version_xml")
class GetVersionXmlAction(ActionHandler):
    """Fetch a bounded byte range of the official XML source for a version."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        version_id = inputs["version_id"]
        offset = inputs.get("offset", 0)
        max_bytes = inputs.get("max_bytes", DEFAULT_XML_CHUNK_BYTES)
        try:
            if inputs.get("source") is None:
                version_response = await _get_version_response(version_id, context)
                version = _version(_object_response(version_response.data))
                if version["version_id"] != version_id:
                    raise LegislationError(
                        "The New Zealand Legislation API returned a different version than requested."
                    )
                _trusted_xml_url(version["formats"])
                source_url = _canonical_xml_url(version_id)
                source = {
                    "version_id": version_id,
                    "source_url": source_url,
                }
                rate_limit = _rate_limit(version_response.headers)
            else:
                source = _continued_xml_source(inputs["source"], version_id)
                source_url = source["source_url"]
                rate_limit = {"limit": None, "remaining": None, "reset_at": None}
            xml, returned_bytes, total_bytes, next_offset = await _fetch_xml_chunk(source_url, offset, max_bytes)
            return ActionResult(
                data={
                    "source": source,
                    "xml": xml,
                    "offset": offset,
                    "returned_bytes": returned_bytes,
                    "total_bytes": total_bytes,
                    "truncated": next_offset is not None,
                    "next_offset": next_offset,
                    "rate_limit": rate_limit,
                }
            )
        except LegislationError as exc:
            return ActionError(message=str(exc))
        except HTTPError as exc:
            return _http_error(exc, resource="version")
        except (aiohttp.ClientError, TimeoutError):
            return ActionError(message="The New Zealand Legislation website could not provide the XML document.")
        except Exception as exc:
            return _unexpected_error(context, "get_version_xml", exc)
