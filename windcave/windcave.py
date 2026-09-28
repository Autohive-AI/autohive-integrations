"""Read-only Windcave REST API integration."""

import base64
from typing import Any
from urllib.parse import quote

import aiohttp

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    FetchResponse,
    HTTPError,
    Integration,
)

windcave = Integration.load()

BASE_URL = "https://sec.windcave.com/api/v1"
REQUEST_TIMEOUT_SECONDS = 30
REDACTED_VALUE = "[REDACTED]"
CARD_FIELDS = frozenset(
    {
        "card",
        "cards",
        "cardid",
        "cardnumber2",
        "cardnumber",
        "cardholdername",
        "dateexpirymonth",
        "dateexpiryyear",
        "cvc",
        "cvc2",
        "cvv",
    }
)
SAFE_API_MESSAGES = frozenset(
    {
        "Invalid session id",
        "Invalid transaction id",
        "Session not found",
        "Transaction not found",
    }
)


class WindcaveCredentialsError(ValueError):
    """Credential validation failure with a safe, fixed message."""


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> dict[str, str]:
    """
    Build authentication headers for Windcave REST API requests.
    Windcave uses HTTP Basic Authentication with the REST API username and API key.
    """
    credentials = context.auth.get("credentials", {})
    username = credentials.get("username")
    api_key = credentials.get("api_key")

    if not isinstance(username, str) or not username.strip():
        raise WindcaveCredentialsError("Windcave REST API username is required")
    if not isinstance(api_key, str) or not api_key.strip():
        raise WindcaveCredentialsError("Windcave REST API key is required")

    if not username.isascii() or not api_key.isascii():
        raise WindcaveCredentialsError("Windcave REST API credentials must contain only ASCII characters")

    auth_bytes = f"{username}:{api_key}".encode("ascii")
    basic_auth = base64.b64encode(auth_bytes).decode("ascii")

    return {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/json"}


def extract_error_message(error: HTTPError) -> str:
    """Return only known lookup messages; never echo upstream payloads."""
    data = error.response_data
    if isinstance(data, dict):
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            messages = [e.get("message") if isinstance(e, dict) else e for e in errors]
            if all(isinstance(message, str) and message in SAFE_API_MESSAGES for message in messages):
                return "; ".join(messages)
        message = data.get("message")
        if isinstance(message, str) and message in SAFE_API_MESSAGES:
            return message
    return f"Windcave API request failed (HTTP {error.status})"


def _redact_value(value: Any) -> Any:
    """Preserve a value's container shape while redacting all scalar data."""
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if value is None:
        return None
    return REDACTED_VALUE


def redact_card_objects(value: Any) -> Any:
    """Redact card objects and standalone card credentials at every depth."""
    if isinstance(value, dict):
        return {
            key: _redact_value(item) if key.lower() in CARD_FIELDS else redact_card_objects(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_card_objects(item) for item in value]
    return value


async def _windcave_request(url: str, *, headers: dict[str, str], method: str = "GET") -> FetchResponse:
    """Bypass SDK response logging, redacting data before it leaves transport.

    One request, no retries. Redirects are disabled to avoid forwarding auth or
    following a provider redirect outside the fixed Windcave endpoint.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout, raise_for_status=False) as session:
            async with session.request(method, url, headers=headers, allow_redirects=False, ssl=True) as response:
                try:
                    data = await response.json(content_type=None)
                except (ValueError, UnicodeError):
                    data = None
                if not 200 <= response.status < 300:
                    message = extract_error_message(HTTPError(response.status, "", data))
                    # Only a curated message leaves transport; never the raw body.
                    raise HTTPError(response.status, message, {"message": message}) from None
                if not isinstance(data, dict):
                    raise ValueError("Invalid Windcave response")
                return FetchResponse(status=response.status, headers={}, data=redact_card_objects(data))
    except HTTPError:
        raise
    except Exception:
        # aiohttp and parser exceptions can contain sensitive response details.
        raise RuntimeError("Windcave request failed") from None


# ---- Transaction Action Handlers ----


@windcave.action("get_transaction")
class GetTransactionAction(ActionHandler):
    """Retrieve a Windcave transaction by ID."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> Any:
        try:
            transaction_id = quote(inputs["transaction_id"], safe="")

            response = await _windcave_request(
                f"{BASE_URL}/transactions/{transaction_id}",
                method="GET",
                headers=get_auth_headers(context),
            )
            transaction = redact_card_objects(response.data or {})

            return ActionResult(
                data={
                    "transaction_id": transaction.get("id"),
                    "authorised": transaction.get("authorised"),
                    "settlement_date": transaction.get("settlementDate"),
                    "amount_surcharge": transaction.get("amountSurcharge"),
                    "transaction": transaction,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except WindcaveCredentialsError as e:
            return ActionError(message=str(e))
        except Exception:
            return ActionError(message="Unable to retrieve the Windcave transaction. Please try again.")


# ---- Session Action Handlers ----


@windcave.action("get_session")
class GetSessionAction(ActionHandler):
    """Retrieve a Windcave payment session by ID with card data redacted."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> Any:
        try:
            session_id = quote(inputs["session_id"], safe="")

            response = await _windcave_request(
                f"{BASE_URL}/sessions/{session_id}",
                method="GET",
                headers=get_auth_headers(context),
            )
            session = redact_card_objects(response.data or {})

            return ActionResult(
                data={
                    "session_id": session.get("id"),
                    "state": session.get("state"),
                    "type": session.get("type"),
                    "amount": session.get("amount"),
                    "currency": session.get("currency"),
                    "merchant_reference": session.get("merchantReference"),
                    "expires": session.get("expires"),
                    "transactions": session.get("transactions") or [],
                    "session": session,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except WindcaveCredentialsError as e:
            return ActionError(message=str(e))
        except Exception:
            return ActionError(message="Unable to retrieve the Windcave session. Please try again.")
