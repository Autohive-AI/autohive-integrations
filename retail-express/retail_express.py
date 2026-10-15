from typing import Dict, Any

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

# Create the integration using the config.json
retail_express = Integration.load()

# Base URL for Retail Express API
RETAIL_EXPRESS_API_BASE_URL = "https://api.retailexpress.com.au"
API_VERSION = "v2.1"


# ---- Helper Functions ----


async def get_access_token(context: ExecutionContext) -> str:
    """
    Get a valid access token for Retail Express API.
    The API key is exchanged for a Bearer token on each request.

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Valid access token string
    """
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")

    # Request new token - API key is always exchanged for Bearer token
    response = await context.fetch(
        f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/auth/token",
        method="GET",
        headers={"x-api-key": api_key, "Accept": "application/json"},
    )

    return response.data.get("access_token", "")


async def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Retail Express API requests.
    Retail Express requires both x-api-key and Bearer token.

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with Authorization and x-api-key headers
    """
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")

    access_token = await get_access_token(context)

    return {
        "Authorization": f"Bearer {access_token}",
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def build_pagination_params(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build pagination query parameters."""
    params = {}

    page_number = inputs.get("page_number")
    page_size = inputs.get("page_size")

    if page_number is not None:
        params["page_number"] = page_number
    if page_size is not None:
        params["page_size"] = min(page_size, 250)

    return params


# ---- Product Action Handlers ----


@retail_express.action("list_products")
class ListProductsAction(ActionHandler):
    """Retrieve a paginated list of products from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            sku = inputs.get("sku")
            updated_since = inputs.get("updated_since")
            if sku:
                params["sku"] = sku
            if updated_since:
                params["updated_since"] = updated_since

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/products", method="GET", headers=headers, params=params
            )

            body = response.data
            products = body.get("data", [])

            return ActionResult(
                data={
                    "products": products,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(products)),
                    "result": True,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("get_product")
class GetProductAction(ActionHandler):
    """Retrieve details of a specific product by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            product_id = inputs["product_id"]

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/products/{product_id}", method="GET", headers=headers
            )

            body = response.data
            return ActionResult(data={"product": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Inventory Action Handlers ----


@retail_express.action("list_inventory_levels")
class ListInventoryLevelsAction(ActionHandler):
    """Retrieve current inventory quantities by product and outlet."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            sales_channel_id = inputs.get("sales_channel_id")
            sku = inputs.get("sku")
            outlet_id = inputs.get("outlet_id")
            product_id = inputs.get("product_id")
            modified_since = inputs.get("modified_since")
            order_by = inputs.get("order_by")
            filter_by = inputs.get("filter_by")

            if sales_channel_id:
                params["sales_channel_id"] = sales_channel_id
            if sku:
                params["sku"] = sku
            if outlet_id:
                params["outlet_id"] = outlet_id
            if product_id:
                params["product_id"] = product_id
            if modified_since:
                params["modified_since"] = modified_since
            if order_by:
                params["order_by"] = order_by
            if filter_by:
                params["filter_by"] = filter_by

            headers = await get_auth_headers(context)
            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/inventory",
                method="GET",
                headers=headers,
                params=params,
            )

            body = response.data
            inventory_levels = body.get("data", [])
            return ActionResult(
                data={
                    "inventory_levels": inventory_levels,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(inventory_levels)),
                    "result": True,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("list_inventory_movements")
class ListInventoryMovementsAction(ActionHandler):
    """Retrieve inventory movement history for reconciliation and auditing."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            plu = inputs.get("plu")
            reference_ids = inputs.get("reference_ids")
            movement_types = inputs.get("movement_types")
            filter_by = inputs.get("filter_by")
            order_by = inputs.get("order_by")

            if plu:
                params["plu"] = plu
            if reference_ids:
                params["reference_ids"] = reference_ids
            if movement_types:
                params["movement_types"] = movement_types
            if filter_by:
                params["filter_by"] = filter_by
            if order_by:
                params["order_by"] = order_by

            headers = await get_auth_headers(context)
            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/inventorymovementlogs",
                method="GET",
                headers=headers,
                params=params,
            )

            body = response.data
            inventory_movements = body.get("data", [])
            return ActionResult(
                data={
                    "inventory_movements": inventory_movements,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(inventory_movements)),
                    "result": True,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ---- Customer Action Handlers ----


@retail_express.action("list_customers")
class ListCustomersAction(ActionHandler):
    """Retrieve a paginated list of customers from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            email = inputs.get("email")
            updated_since = inputs.get("updated_since")
            if email:
                params["email"] = email
            if updated_since:
                params["updated_since"] = updated_since

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers", method="GET", headers=headers, params=params
            )

            body = response.data
            customers = body.get("data", [])

            return ActionResult(
                data={
                    "customers": customers,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(customers)),
                    "result": True,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("get_customer")
class GetCustomerAction(ActionHandler):
    """Retrieve details of a specific customer by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs["customer_id"]

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers/{customer_id}", method="GET", headers=headers
            )

            body = response.data
            return ActionResult(data={"customer": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("create_customer")
class CreateCustomerAction(ActionHandler):
    """Create a new customer in Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"first_name": inputs["first_name"], "last_name": inputs["last_name"]}

            email = inputs.get("email")
            phone = inputs.get("phone")
            mobile = inputs.get("mobile")
            company = inputs.get("company")
            billing_address = inputs.get("billing_address")
            shipping_address = inputs.get("shipping_address")

            if email:
                body["email"] = email
            if phone:
                body["phone"] = phone
            if mobile:
                body["mobile"] = mobile
            if company:
                body["company"] = company
            if billing_address:
                body["billing_address"] = billing_address
            if shipping_address:
                body["shipping_address"] = shipping_address

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers", method="POST", headers=headers, json=body
            )

            body = response.data
            return ActionResult(data={"customer": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("update_customer")
class UpdateCustomerAction(ActionHandler):
    """Update an existing customer's information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs["customer_id"]
            body = {}

            first_name = inputs.get("first_name")
            last_name = inputs.get("last_name")
            email = inputs.get("email")
            phone = inputs.get("phone")
            mobile = inputs.get("mobile")
            company = inputs.get("company")

            if first_name:
                body["first_name"] = first_name
            if last_name:
                body["last_name"] = last_name
            if email:
                body["email"] = email
            if phone:
                body["phone"] = phone
            if mobile:
                body["mobile"] = mobile
            if company:
                body["company"] = company

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="PUT",
                headers=headers,
                json=body,
            )

            body = response.data
            return ActionResult(data={"customer": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Order Action Handlers ----


@retail_express.action("list_orders")
class ListOrdersAction(ActionHandler):
    """Retrieve a paginated list of orders from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            status = inputs.get("status")
            customer_id = inputs.get("customer_id")
            updated_since = inputs.get("updated_since")
            if status:
                params["status"] = status
            if customer_id:
                params["customer_id"] = customer_id
            if updated_since:
                params["updated_since"] = updated_since

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/orders", method="GET", headers=headers, params=params
            )

            body = response.data
            orders = body.get("data", [])

            return ActionResult(
                data={
                    "orders": orders,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(orders)),
                    "result": True,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("get_order")
class GetOrderAction(ActionHandler):
    """Retrieve details of a specific order by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            order_id = inputs["order_id"]

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/orders/{order_id}", method="GET", headers=headers
            )

            body = response.data
            return ActionResult(data={"order": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Outlet Action Handlers ----


@retail_express.action("list_outlets")
class ListOutletsAction(ActionHandler):
    """Retrieve a list of all outlets (store locations) from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/outlets", method="GET", headers=headers, params=params
            )

            body = response.data
            outlets = body.get("data", [])

            return ActionResult(
                data={
                    "outlets": outlets,
                    "page_number": body.get("page_number", 1),
                    "page_size": body.get("page_size", 20),
                    "total_records": body.get("total_records", len(outlets)),
                    "result": True,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@retail_express.action("get_outlet")
class GetOutletAction(ActionHandler):
    """Retrieve details of a specific outlet by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            outlet_id = inputs["outlet_id"]

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/outlets/{outlet_id}", method="GET", headers=headers
            )

            body = response.data
            return ActionResult(data={"outlet": body.get("data", body), "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
