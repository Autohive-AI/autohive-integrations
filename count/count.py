import hashlib
import hmac
import time
from typing import Any, Dict

from autohive_integrations_sdk import ActionHandler, ActionResult, Integration

count = Integration.load()

BASE_URL = "https://api.getcount.com"


def _headers(context: Any) -> Dict[str, str]:
    credentials = context.auth.get("credentials", {})
    access_token = credentials.get("access_token", "")
    client_id = context.auth.get("client_id", "")
    client_secret = context.auth.get("client_secret", "")
    timestamp = str(int(time.time()))
    signature = (
        hmac.new(
            client_secret.encode(),
            f"{client_id}{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if client_secret
        else ""
    )
    return {
        "Authorization": f"Bearer {access_token}",
        "x-client-id": client_id,
        "x-timestamp": timestamp,
        "x-signature": signature,
        "Content-Type": "application/json",
    }


async def _fetch(context: Any, url: str, *, method: str = "GET", json: Any = None, params: Any = None) -> Any:
    resp = await context.fetch(url, method=method, json=json, headers=_headers(context), params=params)
    if resp.status >= 400:
        msg = resp.data.get("message", str(resp.data)) if isinstance(resp.data, dict) else str(resp.data)
        raise Exception(f"Count API error {resp.status}: {msg}")
    return resp.data


def _data(resp: Any) -> Any:
    return resp.get("data", resp) if isinstance(resp, dict) else resp


@count.action("list_accounts")
class ListAccountsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/accounts", params=params)
            return ActionResult(data={"result": True, "accounts": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "accounts": [], "error": str(e)}, cost_usd=0.0)


@count.action("create_account")
class CreateAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/accounts", method="POST", json=inputs)
            return ActionResult(data={"result": True, "account": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "account": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_account")
class UpdateAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("account_uuid")
            resp = await _fetch(context, f"{BASE_URL}/accounts/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "account": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "account": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_account")
class DeleteAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/accounts/{inputs['account_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("list_customers")
class ListCustomersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/customers", params=params)
            return ActionResult(data={"result": True, "customers": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "customers": [], "error": str(e)}, cost_usd=0.0)


@count.action("get_customer")
class GetCustomerAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/customers/{inputs['customer_uuid']}")
            return ActionResult(data={"result": True, "customer": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "customer": {}, "error": str(e)}, cost_usd=0.0)


@count.action("find_customer_by_email")
class FindCustomerByEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/customers/find-by-email", params={"email": inputs["email"]})
            return ActionResult(data={"result": True, "customer": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "customer": {}, "error": str(e)}, cost_usd=0.0)


@count.action("create_customer")
class CreateCustomerAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/customers", method="POST", json=inputs)
            return ActionResult(data={"result": True, "customer": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "customer": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_customer")
class UpdateCustomerAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("customer_uuid")
            resp = await _fetch(context, f"{BASE_URL}/customers/{uuid}", method="PUT", json=inputs)
            return ActionResult(data={"result": True, "customer": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "customer": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_customer")
class DeleteCustomerAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/customers/{inputs['customer_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("list_vendors")
class ListVendorsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/vendors", params=params)
            return ActionResult(data={"result": True, "vendors": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "vendors": [], "error": str(e)}, cost_usd=0.0)


@count.action("create_vendor")
class CreateVendorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/vendors", method="POST", json=inputs)
            return ActionResult(data={"result": True, "vendor": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "vendor": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_vendor")
class UpdateVendorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("vendor_uuid")
            resp = await _fetch(context, f"{BASE_URL}/vendors/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "vendor": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "vendor": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_vendor")
class DeleteVendorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/vendors/{inputs['vendor_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("list_products")
class ListProductsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/products", params=params)
            return ActionResult(data={"result": True, "products": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "products": [], "error": str(e)}, cost_usd=0.0)


@count.action("get_product")
class GetProductAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/products/{inputs['product_uuid']}")
            return ActionResult(data={"result": True, "product": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "product": {}, "error": str(e)}, cost_usd=0.0)


@count.action("find_product_by_name")
class FindProductByNameAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/products/find-by-name", params={"name": inputs["name"]})
            return ActionResult(data={"result": True, "product": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "product": {}, "error": str(e)}, cost_usd=0.0)


@count.action("create_product")
class CreateProductAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/products", method="POST", json=inputs)
            return ActionResult(data={"result": True, "product": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "product": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_product")
class UpdateProductAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("product_uuid")
            resp = await _fetch(context, f"{BASE_URL}/products/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "product": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "product": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_product")
class DeleteProductAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/products/{inputs['product_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("list_transactions")
class ListTransactionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/transactions", params=params)
            return ActionResult(data={"result": True, "transactions": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "transactions": [], "error": str(e)}, cost_usd=0.0)


@count.action("create_transaction")
class CreateTransactionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/transactions", method="POST", json=inputs)
            return ActionResult(data={"result": True, "transaction": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "transaction": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_transaction")
class UpdateTransactionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("transaction_uuid")
            resp = await _fetch(context, f"{BASE_URL}/transactions/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "transaction": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "transaction": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_transaction")
class DeleteTransactionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/transactions/{inputs['transaction_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("get_invoice")
class GetInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/invoices/{inputs['invoice_uuid']}")
            return ActionResult(data={"result": True, "invoice": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "invoice": {}, "error": str(e)}, cost_usd=0.0)


@count.action("create_invoice")
class CreateInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/invoices", method="POST", json=inputs)
            return ActionResult(data={"result": True, "invoice": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "invoice": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_invoice")
class UpdateInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("invoice_uuid")
            resp = await _fetch(context, f"{BASE_URL}/invoices/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "invoice": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "invoice": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_invoice")
class DeleteInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/invoices/{inputs['invoice_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("create_bill")
class CreateBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/bills", method="POST", json=inputs)
            return ActionResult(data={"result": True, "bill": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "bill": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_bill")
class UpdateBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("bill_uuid")
            resp = await _fetch(context, f"{BASE_URL}/bills/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "bill": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "bill": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_bill")
class DeleteBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/bills/{inputs['bill_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("approve_bill")
class ApproveBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/bills/{inputs['bill_uuid']}/approve", method="POST")
            return ActionResult(data={"result": True, "bill": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "bill": {}, "error": str(e)}, cost_usd=0.0)


@count.action("list_journal_entries")
class ListJournalEntriesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/journal-entries", params=params)
            return ActionResult(data={"result": True, "journal_entries": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "journal_entries": [], "error": str(e)}, cost_usd=0.0)


@count.action("create_journal_entry")
class CreateJournalEntryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/journal-entries", method="POST", json=inputs)
            return ActionResult(data={"result": True, "journal_entry": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "journal_entry": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_journal_entry")
class UpdateJournalEntryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("journal_entry_uuid")
            resp = await _fetch(context, f"{BASE_URL}/journal-entries/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "journal_entry": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "journal_entry": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_journal_entry")
class DeleteJournalEntryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/journal-entries/{inputs['journal_entry_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("list_tags")
class ListTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/tags", params=params)
            return ActionResult(data={"result": True, "tags": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "tags": [], "error": str(e)}, cost_usd=0.0)


@count.action("create_tag")
class CreateTagAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            resp = await _fetch(context, f"{BASE_URL}/tags", method="POST", json=inputs)
            return ActionResult(data={"result": True, "tag": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "tag": {}, "error": str(e)}, cost_usd=0.0)


@count.action("update_tag")
class UpdateTagAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            uuid = inputs.pop("tag_uuid")
            resp = await _fetch(context, f"{BASE_URL}/tags/{uuid}", method="PATCH", json=inputs)
            return ActionResult(data={"result": True, "tag": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "tag": {}, "error": str(e)}, cost_usd=0.0)


@count.action("delete_tag")
class DeleteTagAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            await _fetch(context, f"{BASE_URL}/tags/{inputs['tag_uuid']}", method="DELETE")
            return ActionResult(data={"result": True, "deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "deleted": False, "error": str(e)}, cost_usd=0.0)


@count.action("get_trial_balance")
class GetTrialBalanceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/reports/trial-balance", params=params)
            return ActionResult(data={"result": True, "report": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "report": {}, "error": str(e)}, cost_usd=0.0)


@count.action("get_balance_sheet")
class GetBalanceSheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/reports/balance-sheet", params=params)
            return ActionResult(data={"result": True, "report": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "report": {}, "error": str(e)}, cost_usd=0.0)


@count.action("get_profit_and_loss")
class GetProfitAndLossAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: Any):
        try:
            params = {k: v for k, v in inputs.items() if v is not None}
            resp = await _fetch(context, f"{BASE_URL}/reports/profit-and-loss", params=params)
            return ActionResult(data={"result": True, "report": _data(resp)}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "report": {}, "error": str(e)}, cost_usd=0.0)
