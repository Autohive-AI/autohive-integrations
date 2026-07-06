"""
Windcave — payment gateway integration for the Windcave REST API.

Actions:
- create_session: Create a Hosted Payment Page (HPP) session.
- get_session: Retrieve a session and its transaction outcome.
- create_transaction: Run a direct transaction against a stored card token.
- get_transaction: Retrieve a transaction by ID.
- complete_transaction: Capture a prior 'auth' transaction.
- refund_transaction: Refund a prior purchase/completed transaction.
- void_transaction: Void a prior transaction before settlement.
"""

import base64
from typing import Any, Dict, Optional

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

windcave = Integration.load()

PRODUCTION_BASE_URL = "https://sec.windcave.com/api/v1"
UAT_BASE_URL = "https://uat.windcave.com/api/v1"


# ---- Helper Functions ----


def get_base_url(context: ExecutionContext) -> str:
    """Return the Windcave API base URL for the configured environment."""
    if context.auth.get("use_test_environment"):
        return UAT_BASE_URL
    return PRODUCTION_BASE_URL


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Windcave REST API requests.
    Windcave uses HTTP Basic Authentication with the REST API username and API key.
    """
    username = context.auth.get("username", "")
    api_key = context.auth.get("api_key", "")

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


def format_amount(amount: Any) -> str:
    """Format a numeric amount as the string Windcave expects, e.g. 19.99 -> '19.99'."""
    return f"{float(amount):.2f}"


def find_link(obj: Dict[str, Any], rel: str) -> Optional[str]:
    """Find the href for a given rel in a Windcave links array."""
    for link in obj.get("links", []) or []:
        if link.get("rel") == rel:
            return link.get("href")
    return None


def latest_transaction(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the most recent transaction attempt from a session, if any."""
    transactions = session.get("transactions") or []
    return transactions[0] if transactions else None


# ---- Session Action Handlers ----


@windcave.action("create_session")
class CreateSessionAction(ActionHandler):
    """Create a Windcave Hosted Payment Page (HPP) session."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            session_type = inputs.get("type", "purchase")

            if session_type in ("purchase", "auth") and inputs.get("amount") is None:
                return ActionError(message=f"'amount' is required for session type '{session_type}'.")

            body: Dict[str, Any] = {
                "type": session_type,
                "currency": inputs["currency"],
                "merchantReference": inputs["merchant_reference"],
            }

            if inputs.get("amount") is not None:
                body["amount"] = format_amount(inputs["amount"])
            if inputs.get("amount_surcharge") is not None:
                body["amountSurcharge"] = format_amount(inputs["amount_surcharge"])
            if inputs.get("methods"):
                body["methods"] = inputs["methods"]
            if inputs.get("store_card") is not None:
                body["storeCard"] = inputs["store_card"]
            if inputs.get("language"):
                body["language"] = inputs["language"]

            callback_urls = {}
            if inputs.get("approved_callback_url"):
                callback_urls["approved"] = inputs["approved_callback_url"]
            if inputs.get("declined_callback_url"):
                callback_urls["declined"] = inputs["declined_callback_url"]
            if inputs.get("cancelled_callback_url"):
                callback_urls["cancelled"] = inputs["cancelled_callback_url"]
            if callback_urls:
                body["callbackUrls"] = callback_urls

            if inputs.get("notification_url"):
                body["notificationUrl"] = inputs["notification_url"]

            response = await context.fetch(
                f"{get_base_url(context)}/sessions",
                method="POST",
                headers=get_auth_headers(context),
                json=body,
            )
            session = response.data or {}

            return ActionResult(
                data={
                    "session_id": session.get("id"),
                    "state": session.get("state"),
                    "hpp_url": find_link(session, "hpp"),
                    "session": session,
                    "result": True,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@windcave.action("get_session")
class GetSessionAction(ActionHandler):
    """Retrieve a Windcave session by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            session_id = inputs["session_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/sessions/{session_id}",
                method="GET",
                headers=get_auth_headers(context),
            )
            session = response.data or {}
            transaction = latest_transaction(session)

            return ActionResult(
                data={
                    "session_id": session.get("id"),
                    "state": session.get("state"),
                    "authorised": transaction.get("authorised") if transaction else None,
                    "settlement_date": transaction.get("settlementDate") if transaction else None,
                    "amount_surcharge": transaction.get("amountSurcharge") if transaction else None,
                    "transactions": session.get("transactions", []),
                    "session": session,
                    "result": True,
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Transaction Action Handlers ----


@windcave.action("create_transaction")
class CreateTransactionAction(ActionHandler):
    """Create a direct, merchant-initiated transaction against a stored card token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            transaction_type = inputs.get("type", "purchase")

            if transaction_type in ("purchase", "auth") and inputs.get("amount") is None:
                return ActionError(message=f"'amount' is required for transaction type '{transaction_type}'.")

            body: Dict[str, Any] = {
                "type": transaction_type,
                "currency": inputs["currency"],
                "merchantReference": inputs["merchant_reference"],
                "cardId": inputs["card_id"],
            }
            if inputs.get("amount") is not None:
                body["amount"] = format_amount(inputs["amount"])
            if inputs.get("amount_surcharge") is not None:
                body["amountSurcharge"] = format_amount(inputs["amount_surcharge"])

            response = await context.fetch(
                f"{get_base_url(context)}/transactions",
                method="POST",
                headers=get_auth_headers(context),
                json=body,
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


@windcave.action("get_transaction")
class GetTransactionAction(ActionHandler):
    """Retrieve a Windcave transaction by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            transaction_id = inputs["transaction_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/transactions/{transaction_id}",
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


@windcave.action("complete_transaction")
class CompleteTransactionAction(ActionHandler):
    """Complete a prior 'auth' transaction, capturing the reserved funds."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            body: Dict[str, Any] = {
                "type": "complete",
                "transaction": {"id": inputs["transaction_id"]},
            }
            if inputs.get("amount") is not None:
                body["amount"] = format_amount(inputs["amount"])
            if inputs.get("amount_surcharge") is not None:
                body["amountSurcharge"] = format_amount(inputs["amount_surcharge"])
            if inputs.get("merchant_reference"):
                body["merchantReference"] = inputs["merchant_reference"]

            response = await context.fetch(
                f"{get_base_url(context)}/transactions",
                method="POST",
                headers=get_auth_headers(context),
                json=body,
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


@windcave.action("refund_transaction")
class RefundTransactionAction(ActionHandler):
    """Refund a prior purchase or completed transaction, in full or in part."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            body: Dict[str, Any] = {
                "type": "refund",
                "transaction": {"id": inputs["transaction_id"]},
            }
            if inputs.get("amount") is not None:
                body["amount"] = format_amount(inputs["amount"])
            if inputs.get("amount_surcharge") is not None:
                body["amountSurcharge"] = format_amount(inputs["amount_surcharge"])
            if inputs.get("merchant_reference"):
                body["merchantReference"] = inputs["merchant_reference"]

            response = await context.fetch(
                f"{get_base_url(context)}/transactions",
                method="POST",
                headers=get_auth_headers(context),
                json=body,
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


@windcave.action("void_transaction")
class VoidTransactionAction(ActionHandler):
    """Void a prior transaction before it settles."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            body: Dict[str, Any] = {
                "type": "void",
                "transaction": {"id": inputs["transaction_id"]},
            }
            if inputs.get("merchant_reference"):
                body["merchantReference"] = inputs["merchant_reference"]

            response = await context.fetch(
                f"{get_base_url(context)}/transactions",
                method="POST",
                headers=get_auth_headers(context),
                json=body,
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
