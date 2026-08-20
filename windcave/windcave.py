"""
Windcave — payment gateway integration for the Windcave REST API.

Actions:
- get_transaction: Retrieve a transaction by ID.
"""

import base64
from typing import Any, Dict

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

windcave = Integration.load()

BASE_URL = "https://sec.windcave.com/api/v1"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Windcave REST API requests.
    Windcave uses HTTP Basic Authentication with the REST API username and API key.
    """
    credentials = context.auth["credentials"]
    username = credentials.get("username", "")
    api_key = credentials.get("api_key", "")

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


# ---- Transaction Action Handlers ----


@windcave.action("get_transaction")
class GetTransactionAction(ActionHandler):
    """Retrieve a Windcave transaction by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            transaction_id = inputs["transaction_id"]

            response = await context.fetch(
                f"{BASE_URL}/transactions/{transaction_id}",
                method="GET",
                headers=get_auth_headers(context),
            )
            transaction = response.data or {}

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
