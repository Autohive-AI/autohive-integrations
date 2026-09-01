"""
Windcave — payment gateway integration for the Windcave REST API.

Actions:
- get_transaction: Retrieve a transaction by ID.
- get_session: Retrieve a payment session by ID with card data redacted.
"""

import base64
from typing import Any, Dict
from urllib.parse import quote

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

windcave = Integration.load()

BASE_URL = "https://uat.windcave.com/api/v1"
REDACTED_VALUE = "[REDACTED]"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Windcave REST API requests.
    Windcave uses HTTP Basic Authentication with the REST API username and API key.
    """
    credentials = context.auth.get("credentials", {})
    username = credentials.get("username")
    api_key = credentials.get("api_key")

    if not isinstance(username, str) or not username.strip():
        raise ValueError("Windcave REST API username is required")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Windcave REST API key is required")

    auth_bytes = f"{username}:{api_key}".encode("ascii")
    basic_auth = base64.b64encode(auth_bytes).decode("ascii")

    return {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/json"}


def extract_error_message(error: HTTPError) -> str:
    """Extract a human-readable error message from a Windcave error response."""
    data = error.response_data
    if isinstance(data, dict):
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            messages = [e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors]
            return "; ".join(messages)
        if data.get("message"):
            return str(data["message"])
    return f"Windcave API error (HTTP {error.status}): {error.message}"


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
    """Return a copy with every Windcave card object recursively redacted."""
    if isinstance(value, dict):
        return {
            key: _redact_value(item) if key.lower() == "card" else redact_card_objects(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_card_objects(item) for item in value]
    return value


# ---- Transaction Action Handlers ----


@windcave.action("get_transaction")
class GetTransactionAction(ActionHandler):
    """Retrieve a Windcave transaction by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            transaction_id = quote(inputs["transaction_id"], safe="")

            response = await context.fetch(
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
                    "result": True,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Session Action Handlers ----


@windcave.action("get_session")
class GetSessionAction(ActionHandler):
    """Retrieve a Windcave payment session by ID with card data redacted."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            session_id = quote(inputs["session_id"], safe="")

            response = await context.fetch(
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
                    "result": True,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))
