"""Business Central purchasing, inventory planning, billing and finance actions."""

import asyncio
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID

import aiohttp
from aiohttp import ClientError
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, FetchResponse, Integration

businesscentral = Integration.load(Path(__file__).with_name("config.json"))
HOST = "https://api.businesscentral.dynamics.com"
MAX_HISTORY_ROWS = 10000


class BusinessCentralError(ValueError):
    """Expected validation or provider failure safe to show to users."""


def guid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise BusinessCentralError("Company, tenant, item and document IDs must be UUIDs.") from exc


def base_url(inputs, company=True):
    tenant = guid(inputs["tenant_id"])
    environment = inputs["environment"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,99}", environment):
        raise BusinessCentralError("Invalid Business Central environment name.")
    url = f"{HOST}/v2.0/{tenant}/{quote(environment, safe='')}/api/v2.0"
    if company:
        url += f"/companies({guid(inputs['company_id'])})"
    return url


def continuation(link, resource_url):
    """Never send platform credentials to another host, company or resource."""
    if not isinstance(link, str) or any(c in link for c in ("\\", "\r", "\n", "\t")):
        raise BusinessCentralError("Invalid continuation URL.")
    try:
        actual, expected = urlsplit(link), urlsplit(resource_url)
    except ValueError as exc:
        raise BusinessCentralError("Invalid continuation URL.") from exc
    if actual.scheme != "https" or actual.netloc != expected.netloc or actual.path != expected.path or actual.fragment:
        raise BusinessCentralError("Continuation URL must match the selected environment, company and resource.")
    return link


def odata_string(value):
    return "'" + value.replace("'", "''") + "'"


def date_range(start, end):
    try:
        start = date.fromisoformat(start) if start else None
        end = date.fromisoformat(end) if end else None
    except ValueError as exc:
        raise BusinessCentralError("Dates must use YYYY-MM-DD.") from exc
    if start and end and start > end:
        raise BusinessCentralError("start_date must be on or before end_date.")
    return start, end


def filters(inputs, fields=(), date_field=None):
    clauses = []
    for input_name, api_name, is_guid in fields:
        if inputs.get(input_name) is not None:
            value = guid(inputs[input_name]) if is_guid else odata_string(inputs[input_name])
            clauses.append(f"{api_name} eq {value}")
    if date_field:
        if date_field == "dateFilter" and (not inputs.get("start_date") or not inputs.get("end_date")):
            raise BusinessCentralError(
                "Financial reports require non-empty start_date and end_date in YYYY-MM-DD format."
            )
        start, end = date_range(inputs.get("start_date"), inputs.get("end_date"))
        if start:
            clauses.append(f"{date_field} ge {start.isoformat()}")
        if end:
            clauses.append(f"{date_field} le {end.isoformat()}")
    return " and ".join(clauses)


def http_message(status):
    messages = {
        401: "Reconnect Business Central: the access token is missing, expired or has the wrong audience.",
        403: "Business Central access denied. Check consent and company/object permissions.",
        404: "Business Central resource not found. Check the environment, company and record IDs.",
        429: "Business Central is throttling requests. Retry this action later.",
    }
    return messages.get(status, f"Business Central request failed (HTTP {status}).")


async def request(context, url, *, method="GET", headers=None, json=None, params=None):
    """Keep provider bodies and request details out of SDK error logging.

    The ExecutionContext owns and closes its session. Reuse it for paged reads,
    but disable aiohttp's implicit replay so a DELETE with a lost response is
    never sent twice. Only get_json may retry, and only for reads.
    """
    token = context.auth.get("credentials", {}).get("access_token")
    if not token:
        raise BusinessCentralError("Connect a Business Central OAuth account before running this action.")
    session = getattr(context, "_session", None)
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        context._session = session
    # aiohttp 3.x has no public switch for connection replay. Fail closed if
    # this compatibility dependency changes; keep it covered by a socket test.
    if not hasattr(session, "_retry_connection"):
        raise BusinessCentralError("Unsupported HTTP transport: automatic request replay cannot be disabled.")
    session._retry_connection = False
    request_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
    try:
        async with session.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=request_headers,
            timeout=aiohttp.ClientTimeout(total=context.config.get("timeout", 30)),
            allow_redirects=False,
            raise_for_status=False,
            ssl=True,
        ) as response:
            data = None
            # Error bodies can echo personal information. Do not read or parse
            # them; callers need only the status and retry header.
            if response.status in (200, 201):
                try:
                    data = await response.json()
                except (ValueError, UnicodeError, aiohttp.ContentTypeError):
                    message = "Business Central returned an invalid JSON response."
                    if method != "GET":
                        message += " Check Business Central before retrying."
                    raise BusinessCentralError(message) from None
            return FetchResponse(status=response.status, headers=dict(response.headers), data=data)
    except (ClientError, asyncio.TimeoutError):
        # Exception strings may contain URLs, query values or credentials.
        raise ClientError("Business Central connection failed or timed out.") from None
    except BusinessCentralError:
        raise
    except ValueError:
        raise BusinessCentralError("Business Central request could not be prepared.") from None


async def get_json(context, url, params=None, page_size=100):
    if not context.auth.get("credentials", {}).get("access_token"):
        raise BusinessCentralError("Connect a Business Central OAuth account before running this action.")
    # Encode query values once before the read retry loop.
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    for attempt in range(3):
        try:
            response = await request(
                context, url, method="GET", params=None, headers={"Prefer": f"odata.maxpagesize={page_size}"}
            )
            status, headers = response.status, response.headers
        except (ClientError, asyncio.TimeoutError):
            if attempt < 2:
                await asyncio.sleep(2**attempt)
                continue
            raise BusinessCentralError(
                "Business Central connection failed or timed out. Retry this action later."
            ) from None
        if status in (429, 502, 503, 504) and attempt < 2:
            retry_after = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
            try:
                delay = max(0, float(retry_after)) if retry_after is not None else 2**attempt
            except (ValueError, TypeError):
                delay = 2**attempt
            if delay > 10:
                raise BusinessCentralError(http_message(status))
            await asyncio.sleep(delay)
            continue
        if status != 200:
            raise BusinessCentralError(http_message(status))
        if not isinstance(response.data, dict) or "error" in response.data:
            raise BusinessCentralError("Business Central returned an unexpected response.")
        return response.data
    raise BusinessCentralError("Business Central retry limit reached.")


async def read_page(context, url, inputs, filter_expression=""):
    link = inputs.get("next_link")
    params = None
    if link:
        request_url = continuation(link, url)
    else:
        request_url = url
        params = {}
        if filter_expression:
            params["$filter"] = filter_expression
    data = await get_json(context, request_url, params, inputs.get("page_size", 100))
    records = data.get("value")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise BusinessCentralError("Business Central returned an invalid collection.")
    next_link = data.get("@odata.nextLink") or None
    if next_link:
        continuation(next_link, url)
    return {"records": records, "count": len(records), "next_link": next_link, "has_more": bool(next_link)}


async def list_resource(context, inputs, resource, fields=(), date_field=None, company=True):
    try:
        url = f"{base_url(inputs, company)}/{resource}"
        return ActionResult(data=await read_page(context, url, inputs, filters(inputs, fields, date_field)))
    except BusinessCentralError as exc:
        return ActionError(message=str(exc))


async def get_resource(context, inputs, resource, id_field):
    try:
        url = f"{base_url(inputs)}/{resource}({guid(inputs[id_field])})"
        return ActionResult(data={"record": await get_json(context, url)})
    except BusinessCentralError as exc:
        return ActionError(message=str(exc))


async def list_lines(context, inputs, document_resource, line_resource, id_field):
    try:
        resource = f"{document_resource}({guid(inputs[id_field])})/{line_resource}"
        return await list_resource(context, inputs, resource, (("item_id", "itemId", True),))
    except BusinessCentralError as exc:
        return ActionError(message=str(exc))


async def list_child_resource(context, inputs, parent, child, id_field):
    try:
        resource = f"{parent}({guid(inputs[id_field])})/{child}"
        return await list_resource(context, inputs, resource)
    except BusinessCentralError as exc:
        return ActionError(message=str(exc))


async def list_sales_invoices(context, inputs):
    try:
        expression = filters(inputs, (("customer_id", "customerId", True),), "postingDate")
        clauses = [expression] if expression else []
        status = inputs.get("status")
        if inputs.get("outstanding_only"):
            if status and status != "Open":
                raise BusinessCentralError("outstanding_only requires status Open, or no status filter.")
            status = "Open"
            clauses.append("remainingAmount gt 0")
        if status:
            clauses.append(f"status eq {odata_string(status)}")
        if inputs.get("due_before"):
            due_before, _ = date_range(inputs["due_before"], None)
            clauses.append(f"dueDate lt {due_before.isoformat()}")
        url = f"{base_url(inputs)}/salesInvoices"
        return ActionResult(data=await read_page(context, url, inputs, " and ".join(clauses)))
    except BusinessCentralError as exc:
        return ActionError(message=str(exc))


@businesscentral.action("create_purchase_order")
class CreatePurchaseOrderAction(ActionHandler):
    async def execute(self, inputs, context):
        try:
            url = f"{base_url(inputs)}/purchaseOrders"
            if not context.auth.get("credentials", {}).get("access_token"):
                raise BusinessCentralError("Connect a Business Central OAuth account before running this action.")
            if bool(inputs.get("vendor_id")) == bool(inputs.get("vendor_number")):
                raise BusinessCentralError("Supply exactly one of vendor_id or vendor_number.")
            body = {}
            if inputs.get("vendor_id"):
                body["vendorId"] = guid(inputs["vendor_id"])
            else:
                body["vendorNumber"] = inputs["vendor_number"]
            for api_name, raw_date in (
                ("orderDate", inputs.get("order_date")),
                ("postingDate", inputs.get("posting_date")),
                ("requestedReceiptDate", inputs.get("requested_receipt_date")),
            ):
                if raw_date is not None:
                    value, _ = date_range(raw_date, None)
                    body[api_name] = value.isoformat()
            currency_code = inputs.get("currency_code")
            if currency_code is not None:
                body["currencyCode"] = currency_code
            order_lines = inputs.get("lines")
            if order_lines is not None:
                lines = []
                for line in order_lines:
                    row = {"lineType": "Item", "itemId": guid(line["item_id"]), "quantity": line["quantity"]}
                    for name, api_name in (
                        ("direct_unit_cost", "directUnitCost"),
                        ("unit_of_measure_code", "unitOfMeasureCode"),
                        ("description", "description"),
                    ):
                        if name in line:
                            row[api_name] = line[name]
                    lines.append(row)
                body["purchaseOrderLines"] = lines
            try:
                response = await request(
                    context,
                    url,
                    method="POST",
                    json=body,
                )
            except (ClientError, asyncio.TimeoutError):
                raise BusinessCentralError(
                    "Purchase order outcome is unknown. Check Business Central before retrying to avoid duplicates."
                ) from None
            if response.status != 201:
                raise BusinessCentralError(http_message(response.status))
            record = response.data
            if not isinstance(record, dict) or "error" in record or not record.get("id"):
                raise BusinessCentralError(
                    "Business Central returned an unexpected creation response. Check purchase orders before retrying."
                )
            return ActionResult(data={"record": record})
        except BusinessCentralError as exc:
            return ActionError(message=str(exc))


@businesscentral.action("remove_purchase_order")
class RemovePurchaseOrderAction(ActionHandler):
    async def execute(self, inputs, context):
        try:
            order_id = guid(inputs["purchase_order_id"])
            url = f"{base_url(inputs)}/purchaseOrders({order_id})"
            if not context.auth.get("credentials", {}).get("access_token"):
                raise BusinessCentralError("Connect a Business Central OAuth account before running this action.")
            etag = inputs["etag"]
            if not re.fullmatch(r'(?:W/)?"[^"\r\n]+"', etag):
                raise BusinessCentralError(
                    "Supply the exact @odata.etag from get_purchase_order; wildcards are not allowed."
                )
            try:
                response = await request(
                    context,
                    url,
                    method="DELETE",
                    headers={"If-Match": etag},
                )
                status = response.status
            except (ClientError, asyncio.TimeoutError):
                raise BusinessCentralError(
                    "Purchase order removal outcome is unknown. Check Business Central before retrying."
                ) from None
            if status == 412:
                raise BusinessCentralError(
                    "Purchase order changed. Retrieve it again and review it before removing it."
                )
            if status != 204:
                raise BusinessCentralError(http_message(status))
            return ActionResult(data={"purchase_order_id": order_id, "deleted": True})
        except BusinessCentralError as exc:
            return ActionError(message=str(exc))


@businesscentral.action("list_companies")
class ListCompaniesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
            },
            "companies",
            company=False,
        )


@businesscentral.action("get_company_information")
class GetCompanyInformationAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
            },
            "companyInformation",
        )


@businesscentral.action("list_items")
class ListItemsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "item_number": inputs.get("item_number"),
            },
            "items",
            (("item_number", "number", False),),
        )


@businesscentral.action("get_item")
class GetItemAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "item_id": inputs["item_id"],
            },
            "items",
            "item_id",
        )


@businesscentral.action("list_locations")
class ListLocationsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
            },
            "locations",
        )


@businesscentral.action("list_item_variants")
class ListItemVariantsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "item_id": inputs.get("item_id"),
            },
            "itemVariants",
            (("item_id", "itemId", True),),
        )


@businesscentral.action("list_units_of_measure")
class ListUnitsOfMeasureAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
            },
            "unitsOfMeasure",
        )


@businesscentral.action("list_vendors")
class ListVendorsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "vendor_number": inputs.get("vendor_number"),
            },
            "vendors",
            (("vendor_number", "number", False),),
        )


@businesscentral.action("list_item_ledger_entries")
class ListItemLedgerEntriesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
                "item_number": inputs.get("item_number"),
            },
            "itemLedgerEntries",
            (("item_number", "itemNumber", False),),
            "postingDate",
        )


@businesscentral.action("list_purchase_orders")
class ListPurchaseOrdersAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
                "vendor_id": inputs.get("vendor_id"),
            },
            "purchaseOrders",
            (("vendor_id", "vendorId", True),),
            "orderDate",
        )


@businesscentral.action("get_purchase_order")
class GetPurchaseOrderAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "purchase_order_id": inputs["purchase_order_id"],
            },
            "purchaseOrders",
            "purchase_order_id",
        )


@businesscentral.action("list_purchase_order_lines")
class ListPurchaseOrderLinesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_lines(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "item_id": inputs.get("item_id"),
                "purchase_order_id": inputs["purchase_order_id"],
            },
            "purchaseOrders",
            "purchaseOrderLines",
            "purchase_order_id",
        )


@businesscentral.action("list_sales_orders")
class ListSalesOrdersAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
            },
            "salesOrders",
            date_field="orderDate",
        )


@businesscentral.action("get_sales_order")
class GetSalesOrderAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "sales_order_id": inputs["sales_order_id"],
            },
            "salesOrders",
            "sales_order_id",
        )


@businesscentral.action("list_sales_order_lines")
class ListSalesOrderLinesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_lines(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "item_id": inputs.get("item_id"),
                "sales_order_id": inputs["sales_order_id"],
            },
            "salesOrders",
            "salesOrderLines",
            "sales_order_id",
        )


@businesscentral.action("list_purchase_invoices")
class ListPurchaseInvoicesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
                "vendor_id": inputs.get("vendor_id"),
            },
            "purchaseInvoices",
            (("vendor_id", "vendorId", True),),
            "postingDate",
        )


@businesscentral.action("list_purchase_invoice_lines")
class ListPurchaseInvoiceLinesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_lines(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "item_id": inputs.get("item_id"),
                "purchase_invoice_id": inputs["purchase_invoice_id"],
            },
            "purchaseInvoices",
            "purchaseInvoiceLines",
            "purchase_invoice_id",
        )


def decimal_value(value, field):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BusinessCentralError(f"Business Central returned an invalid {field}.") from exc


async def inventory_item(context, inputs):
    item = await get_json(context, f"{base_url(inputs)}/items({guid(inputs['item_id'])})")
    if item.get("type") != "Inventory" or not item.get("number") or not item.get("baseUnitOfMeasureCode"):
        raise BusinessCentralError("Select an Inventory item with an item number and base unit.")
    return item


@businesscentral.action("estimate_reorder_cost")
class EstimateReorderCostAction(ActionHandler):
    async def execute(self, inputs, context):
        try:
            quantity = decimal_value(inputs["quantity"], "quantity")
            item = await inventory_item(context, inputs)
            unit_cost = decimal_value(item.get("unitCost"), "unitCost")
            info = await read_page(context, f"{base_url(inputs)}/companyInformation", {})
            if len(info["records"]) != 1 or not info["records"][0].get("currencyCode"):
                raise BusinessCentralError("Cannot determine the company's local currency.")
            return ActionResult(
                data={
                    "item_id": item["id"],
                    "item_number": item["number"],
                    "quantity": str(quantity),
                    "unit_cost": str(unit_cost),
                    "estimated_cost": str(quantity * unit_cost),
                    "currency_code": info["records"][0]["currencyCode"],
                    "unit_of_measure": item.get("baseUnitOfMeasureCode", ""),
                    "cost_basis": "recorded_item_unit_cost",
                    "limitations": (
                        "Base-unit estimate only; excludes supplier pricing, freight, duties, discounts and tax."
                    ),
                }
            )
        except BusinessCentralError as exc:
            return ActionError(message=str(exc))


@businesscentral.action("forecast_stock")
class ForecastStockAction(ActionHandler):
    async def execute(self, inputs, context):
        try:
            start, end = date_range(inputs["start_date"], inputs["end_date"])
            today = datetime.now(timezone.utc).date()
            if not start or not end or end >= today or (end - start).days >= 730:
                raise BusinessCentralError("Use a completed historical window of 1 to 730 days ending before today.")
            item = await inventory_item(context, inputs)
            snapshot_at = datetime.now(timezone.utc).isoformat()
            url = f"{base_url(inputs)}/itemLedgerEntries"
            expression = (
                f"itemNumber eq {odata_string(item['number'])} and postingDate ge {start.isoformat()} "
                f"and postingDate le {end.isoformat()}"
            )
            page_inputs = {"page_size": 1000}
            seen, row_count, sales_count = set(), 0, 0
            entry_ids = set()
            net_sales = Decimal(0)
            while True:
                page = await read_page(context, url, page_inputs, expression)
                row_count += page["count"]
                if row_count > MAX_HISTORY_ROWS:
                    raise BusinessCentralError("History exceeds 10,000 rows. Choose a shorter window.")
                for row in page["records"]:
                    entry_id = row.get("id")
                    if not entry_id or entry_id in entry_ids:
                        raise BusinessCentralError("History contains missing or repeated entry IDs. Retry the action.")
                    entry_ids.add(entry_id)
                    if row.get("entryType") == "Sale":
                        sales_count += 1
                        net_sales -= decimal_value(row.get("quantity"), "ledger quantity")
                link = page["next_link"]
                if not link:
                    break
                if link in seen or len(seen) >= 100 or row_count >= MAX_HISTORY_ROWS:
                    raise BusinessCentralError("History is incomplete or repeats pages. Choose a shorter window.")
                seen.add(link)
                page_inputs = {"next_link": link, "page_size": 1000}
            daily = max(Decimal(0), net_sales) / Decimal((end - start).days + 1)
            inventory = decimal_value(item.get("inventory"), "inventory")
            demand = daily * inputs["forecast_days"]
            return ActionResult(
                data={
                    "item_id": item["id"],
                    "item_number": item["number"],
                    "snapshot_at": snapshot_at,
                    "history_start": start.isoformat(),
                    "history_end": end.isoformat(),
                    "forecast_days": inputs["forecast_days"],
                    "history_rows": row_count,
                    "sales_entry_count": sales_count,
                    "net_sales_quantity": str(net_sales),
                    "current_inventory": str(inventory),
                    "average_daily_demand": str(daily),
                    "forecast_demand": str(demand),
                    "projected_inventory": str(inventory - demand),
                    "days_of_cover": str(max(Decimal(0), inventory) / daily) if daily else None,
                    "unit_of_measure": item.get("baseUnitOfMeasureCode", ""),
                    "method": "historical_net_sales_daily_average",
                    "limitations": (
                        "Company-wide baseline from current inventory. Sale returns offset shipments; "
                        "negative net demand is floored at zero. Excludes incoming supply, open orders, "
                        "reservations, seasonality, stockout effects, transfers and production demand. "
                        "No sales history is not proof of zero demand."
                    ),
                }
            )
        except BusinessCentralError as exc:
            return ActionError(message=str(exc))


# Finance: client billing, collections and configured dimension analysis.


@businesscentral.action("list_customers")
class ListCustomersAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "customer_number": inputs.get("customer_number"),
            },
            "customers",
            (("customer_number", "number", False),),
            None,
        )


@businesscentral.action("get_customer")
class GetCustomerAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "customer_id": inputs["customer_id"],
            },
            "customers",
            "customer_id",
        )


@businesscentral.action("list_sales_invoices")
class ListSalesInvoicesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_sales_invoices(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "customer_id": inputs.get("customer_id"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
                "status": inputs.get("status"),
                "due_before": inputs.get("due_before"),
                "outstanding_only": inputs.get("outstanding_only", False),
            },
        )


@businesscentral.action("get_sales_invoice")
class GetSalesInvoiceAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "sales_invoice_id": inputs["sales_invoice_id"],
            },
            "salesInvoices",
            "sales_invoice_id",
        )


@businesscentral.action("list_sales_invoice_lines")
class ListSalesInvoiceLinesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_child_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "sales_invoice_id": inputs["sales_invoice_id"],
            },
            "salesInvoices",
            "salesInvoiceLines",
            "sales_invoice_id",
        )


@businesscentral.action("list_sales_credit_memos")
class ListSalesCreditMemosAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "customer_id": inputs.get("customer_id"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
            },
            "salesCreditMemos",
            (("customer_id", "customerId", True),),
            "creditMemoDate",
        )


@businesscentral.action("list_accounts")
class ListAccountsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "account_number": inputs.get("account_number"),
            },
            "accounts",
            (("account_number", "number", False),),
            None,
        )


@businesscentral.action("list_general_ledger_entries")
class ListGeneralLedgerEntriesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs.get("start_date"),
                "end_date": inputs.get("end_date"),
                "account_id": inputs.get("account_id"),
                "document_number": inputs.get("document_number"),
            },
            "generalLedgerEntries",
            (("account_id", "accountId", True), ("document_number", "documentNumber", False)),
            "postingDate",
        )


@businesscentral.action("list_dimensions")
class ListDimensionsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
            },
            "dimensions",
            (),
            None,
        )


@businesscentral.action("list_dimension_values")
class ListDimensionValuesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_child_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "dimension_id": inputs["dimension_id"],
            },
            "dimensions",
            "dimensionValues",
            "dimension_id",
        )


@businesscentral.action("list_general_ledger_entry_dimensions")
class ListGeneralLedgerEntryDimensionsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_child_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "general_ledger_entry_id": inputs["general_ledger_entry_id"],
            },
            "generalLedgerEntries",
            "dimensionSetLines",
            "general_ledger_entry_id",
        )


@businesscentral.action("get_receivables_aging")
class GetReceivablesAgingAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "customer_id": inputs["customer_id"],
            },
            "agedAccountsReceivables",
            "customer_id",
        )


@businesscentral.action("get_payables_aging")
class GetPayablesAgingAction(ActionHandler):
    async def execute(self, inputs, context):
        return await get_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "vendor_id": inputs["vendor_id"],
            },
            "agedAccountsPayables",
            "vendor_id",
        )


@businesscentral.action("get_trial_balance")
class GetTrialBalanceAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs["start_date"],
                "end_date": inputs["end_date"],
            },
            "trialBalances",
            (),
            "dateFilter",
        )


@businesscentral.action("get_income_statement")
class GetIncomeStatementAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_resource(
            context,
            {
                "tenant_id": inputs["tenant_id"],
                "environment": inputs["environment"],
                "company_id": inputs["company_id"],
                "page_size": inputs.get("page_size", 100),
                "next_link": inputs.get("next_link"),
                "start_date": inputs["start_date"],
                "end_date": inputs["end_date"],
            },
            "incomeStatements",
            (),
            "dateFilter",
        )
