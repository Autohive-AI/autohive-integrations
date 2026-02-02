from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler,
    ActionResult
)
from typing import Dict, Any

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
        headers={
            "x-api-key": api_key,
            "Accept": "application/json"
        }
    )

    return response.get('access_token', '')


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
        "Content-Type": "application/json"
    }


def build_pagination_params(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build pagination query parameters."""
    params = {}

    if 'page_number' in inputs:
        params['page_number'] = inputs['page_number']
    if 'page_size' in inputs:
        params['page_size'] = min(inputs['page_size'], 250)

    return params


# ---- Product Action Handlers ----

@retail_express.action("list_products")
class ListProductsAction(ActionHandler):
    """Retrieve a paginated list of products from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            # Add optional filters
            if 'sku' in inputs and inputs['sku']:
                params['sku'] = inputs['sku']
            if 'updated_since' in inputs and inputs['updated_since']:
                params['updated_since'] = inputs['updated_since']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/products",
                method="GET",
                headers=headers,
                params=params
            )

            products = response.get('data', [])

            return ActionResult(
                data={
                    "products": products,
                    "page_number": response.get('page_number', 1),
                    "page_size": response.get('page_size', 20),
                    "total_records": response.get('total_records', len(products)),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "products": [],
                    "page_number": 1,
                    "page_size": 20,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("get_product")
class GetProductAction(ActionHandler):
    """Retrieve details of a specific product by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            product_id = inputs['product_id']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/products/{product_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "product": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "product": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Customer Action Handlers ----

@retail_express.action("list_customers")
class ListCustomersAction(ActionHandler):
    """Retrieve a paginated list of customers from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            # Add optional filters
            if 'email' in inputs and inputs['email']:
                params['email'] = inputs['email']
            if 'updated_since' in inputs and inputs['updated_since']:
                params['updated_since'] = inputs['updated_since']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers",
                method="GET",
                headers=headers,
                params=params
            )

            customers = response.get('data', [])

            return ActionResult(
                data={
                    "customers": customers,
                    "page_number": response.get('page_number', 1),
                    "page_size": response.get('page_size', 20),
                    "total_records": response.get('total_records', len(customers)),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customers": [],
                    "page_number": 1,
                    "page_size": 20,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("get_customer")
class GetCustomerAction(ActionHandler):
    """Retrieve details of a specific customer by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs['customer_id']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "customer": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("create_customer")
class CreateCustomerAction(ActionHandler):
    """Create a new customer in Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "first_name": inputs['first_name'],
                "last_name": inputs['last_name']
            }

            # Add optional fields
            if 'email' in inputs and inputs['email']:
                body['email'] = inputs['email']
            if 'phone' in inputs and inputs['phone']:
                body['phone'] = inputs['phone']
            if 'mobile' in inputs and inputs['mobile']:
                body['mobile'] = inputs['mobile']
            if 'company' in inputs and inputs['company']:
                body['company'] = inputs['company']
            if 'billing_address' in inputs and inputs['billing_address']:
                body['billing_address'] = inputs['billing_address']
            if 'shipping_address' in inputs and inputs['shipping_address']:
                body['shipping_address'] = inputs['shipping_address']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers",
                method="POST",
                headers=headers,
                json=body
            )

            return ActionResult(
                data={
                    "customer": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("update_customer")
class UpdateCustomerAction(ActionHandler):
    """Update an existing customer's information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs['customer_id']
            body = {}

            # Add only provided fields
            if 'first_name' in inputs and inputs['first_name']:
                body['first_name'] = inputs['first_name']
            if 'last_name' in inputs and inputs['last_name']:
                body['last_name'] = inputs['last_name']
            if 'email' in inputs and inputs['email']:
                body['email'] = inputs['email']
            if 'phone' in inputs and inputs['phone']:
                body['phone'] = inputs['phone']
            if 'mobile' in inputs and inputs['mobile']:
                body['mobile'] = inputs['mobile']
            if 'company' in inputs and inputs['company']:
                body['company'] = inputs['company']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="PUT",
                headers=headers,
                json=body
            )

            return ActionResult(
                data={
                    "customer": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Order Action Handlers ----

@retail_express.action("list_orders")
class ListOrdersAction(ActionHandler):
    """Retrieve a paginated list of orders from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            # Add optional filters
            if 'status' in inputs and inputs['status']:
                params['status'] = inputs['status']
            if 'customer_id' in inputs and inputs['customer_id']:
                params['customer_id'] = inputs['customer_id']
            if 'updated_since' in inputs and inputs['updated_since']:
                params['updated_since'] = inputs['updated_since']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/orders",
                method="GET",
                headers=headers,
                params=params
            )

            orders = response.get('data', [])

            return ActionResult(
                data={
                    "orders": orders,
                    "page_number": response.get('page_number', 1),
                    "page_size": response.get('page_size', 20),
                    "total_records": response.get('total_records', len(orders)),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "orders": [],
                    "page_number": 1,
                    "page_size": 20,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("get_order")
class GetOrderAction(ActionHandler):
    """Retrieve details of a specific order by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            order_id = inputs['order_id']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/orders/{order_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "order": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "order": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Outlet Action Handlers ----

@retail_express.action("list_outlets")
class ListOutletsAction(ActionHandler):
    """Retrieve a list of all outlets (store locations) from Retail Express."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_pagination_params(inputs)

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/outlets",
                method="GET",
                headers=headers,
                params=params
            )

            outlets = response.get('data', [])

            return ActionResult(
                data={
                    "outlets": outlets,
                    "page_number": response.get('page_number', 1),
                    "page_size": response.get('page_size', 20),
                    "total_records": response.get('total_records', len(outlets)),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "outlets": [],
                    "page_number": 1,
                    "page_size": 20,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@retail_express.action("get_outlet")
class GetOutletAction(ActionHandler):
    """Retrieve details of a specific outlet by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            outlet_id = inputs['outlet_id']

            headers = await get_auth_headers(context)

            response = await context.fetch(
                f"{RETAIL_EXPRESS_API_BASE_URL}/{API_VERSION}/outlets/{outlet_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "outlet": response.get('data', response),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "outlet": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )
