"""Read-only Business Central inventory, purchasing and demand actions."""

import asyncio
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import UUID

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, HTTPError, Integration

business_central = Integration.load(Path(__file__).with_name("config.json"))
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


async def get_json(context, url, params=None, page_size=100):
    if not context.auth.get("credentials", {}).get("access_token"):
        raise BusinessCentralError("Connect a Business Central OAuth account before running this action.")
    for attempt in range(3):
        try:
            response = await context.fetch(
                url, method="GET", params=params, headers={"Prefer": f"odata.maxpagesize={page_size}"}
            )
            status, headers = response.status, response.headers
        except HTTPError as exc:
            status, headers = exc.status, getattr(exc, "headers", {})
            if hasattr(exc, "retry_after"):
                headers = dict(headers, **{"Retry-After": str(exc.retry_after)})
            response = None
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


@business_central.action("list_companies")
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


@business_central.action("get_company_information")
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


@business_central.action("list_items")
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


@business_central.action("get_item")
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


@business_central.action("list_locations")
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


@business_central.action("list_item_variants")
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


@business_central.action("list_units_of_measure")
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


@business_central.action("list_vendors")
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


@business_central.action("list_item_ledger_entries")
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


@business_central.action("list_purchase_orders")
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


@business_central.action("get_purchase_order")
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


@business_central.action("list_purchase_order_lines")
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


@business_central.action("list_sales_orders")
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


@business_central.action("get_sales_order")
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


@business_central.action("list_sales_order_lines")
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


@business_central.action("list_purchase_invoices")
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


@business_central.action("list_purchase_invoice_lines")
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


@business_central.action("estimate_reorder_cost")
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


@business_central.action("forecast_stock")
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
                page_inputs = {"next_link": link}
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
