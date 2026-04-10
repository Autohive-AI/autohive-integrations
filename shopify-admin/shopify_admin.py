"""
Shopify Admin API Integration
=============================

Provides access to Shopify's Admin API for store management operations.

Supported Operations:
- Customers: list, get, search, create, update
- Orders: list, get, create, cancel
- Products: list, get, create, update
- Inventory: get levels, set levels
- Locations: list, get
- Fulfillments: list, create, update tracking
- Draft Orders: list, create, complete, delete
- Shop: get info

Authentication:
- OAuth 2.0 with access token
- Header: X-Shopify-Access-Token

Rate Limits:
- GraphQL: 100 points/second (1,000 capacity)
- REST: 40 requests/minute

API Version: 2024-10
"""

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

# Create the integration using the config.json
shopify_admin = Integration.load()

# Shopify API version
API_VERSION = "2024-10"


# ============================================================================
# Helper Functions
# ============================================================================

def get_shop_url(context: ExecutionContext) -> str:
    """Extract the shop URL from the context credentials."""
    credentials = context.auth.get('credentials', {})
    shop_url = credentials.get('shop_url', '')
    if shop_url:
        # Remove protocol if present
        shop_url = shop_url.replace('https://', '').replace('http://', '')
        # Remove trailing slash
        shop_url = shop_url.rstrip('/')
    return shop_url


def get_api_url(context: ExecutionContext, endpoint: str = "") -> str:
    """Build Shopify Admin API URL."""
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/admin/api/{API_VERSION}{endpoint}"


def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for Shopify API requests with OAuth token."""
    access_token = context.auth['credentials']['access_token']
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }


def build_query_params(inputs: Dict[str, Any], allowed_params: list) -> Dict[str, Any]:
    """Build query parameters from inputs, filtering only allowed params."""
    params = {}
    for param in allowed_params:
        if param in inputs and inputs[param] is not None and inputs[param] != "":
            params[param] = inputs[param]
    return params


def success_response(**kwargs) -> ActionResult:
    """Build a standardized success response."""
    return ActionResult(data={"success": True, **kwargs}, cost_usd=0)


def error_response(message: str, **kwargs) -> ActionResult:
    """Build a standardized error response."""
    data = {"success": False, "message": str(message)}
    data.update(kwargs)
    return ActionResult(data=data, cost_usd=0)


# ============================================================================
# GraphQL Helper Functions
# ============================================================================

def get_graphql_url(context: ExecutionContext) -> str:
    """Build Shopify GraphQL Admin API URL."""
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/admin/api/{API_VERSION}/graphql.json"


def to_gid(resource_type: str, id: str) -> str:
    """Convert numeric ID to Shopify Global ID format."""
    if str(id).startswith("gid://"):
        return str(id)
    return f"gid://shopify/{resource_type}/{id}"


def from_gid(gid: str) -> str:
    """Extract numeric ID from Shopify Global ID."""
    if not gid or not str(gid).startswith("gid://"):
        return str(gid) if gid else ""
    return gid.split("/")[-1]


async def execute_graphql(context: ExecutionContext, query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query/mutation against Shopify Admin API."""
    url = get_graphql_url(context)
    headers = build_headers(context)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = await context.fetch(url, method="POST", json=payload, headers=headers)

    # Check for GraphQL errors
    if "errors" in response:
        error_messages = [e.get("message", str(e)) for e in response["errors"]]
        raise Exception(f"GraphQL Error: {'; '.join(error_messages)}")

    return response.get("data", {})


def escape_graphql_query_value(value: str) -> str:
    """Escape and quote a value for use in GraphQL query filter strings.

    Values containing spaces or special characters need to be quoted.
    Double quotes within the value are escaped with backslash.
    """
    value = str(value)
    # Escape backslashes first, then double quotes
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    # Always quote the value to handle spaces and special characters safely
    return f'"{escaped}"'


def build_product_query_filter(inputs: Dict[str, Any]) -> str:
    """Build GraphQL query filter string from inputs."""
    filters = []

    if inputs.get('title'):
        # For wildcard search with spaces, format is: title:*"value"*
        title = str(inputs['title']).replace('\\', '\\\\').replace('"', '\\"')
        filters.append(f'title:*"{title}"*')
    if inputs.get('vendor'):
        filters.append(f"vendor:{escape_graphql_query_value(inputs['vendor'])}")
    if inputs.get('product_type'):
        filters.append(f"product_type:{escape_graphql_query_value(inputs['product_type'])}")
    if inputs.get('status'):
        filters.append(f"status:{inputs['status']}")
    if inputs.get('created_at_min'):
        filters.append(f"created_at:>{inputs['created_at_min']}")
    if inputs.get('created_at_max'):
        filters.append(f"created_at:<{inputs['created_at_max']}")

    return " AND ".join(filters) if filters else None


def transform_product_response(graphql_product: dict) -> dict:
    """Transform GraphQL product response to REST-compatible format."""
    if not graphql_product:
        return {}

    product = {
        "id": from_gid(graphql_product.get("id", "")),
        "title": graphql_product.get("title"),
        "handle": graphql_product.get("handle"),
        "body_html": graphql_product.get("descriptionHtml"),
        "vendor": graphql_product.get("vendor"),
        "product_type": graphql_product.get("productType"),
        "status": (graphql_product.get("status") or "").lower(),
        "tags": ", ".join(graphql_product.get("tags", [])) if isinstance(graphql_product.get("tags"), list) else graphql_product.get("tags", ""),
        "created_at": graphql_product.get("createdAt"),
        "updated_at": graphql_product.get("updatedAt"),
    }

    # Transform variants
    variants_data = graphql_product.get("variants", {})
    if isinstance(variants_data, dict):
        variants_data = variants_data.get("nodes", []) or variants_data.get("edges", [])
    if variants_data and isinstance(variants_data[0], dict) and "node" in variants_data[0]:
        variants_data = [e["node"] for e in variants_data]

    product["variants"] = [
        {
            "id": from_gid(v.get("id", "")),
            "title": v.get("title"),
            "price": v.get("price"),
            "compare_at_price": v.get("compareAtPrice"),
            "sku": v.get("sku"),
            "barcode": v.get("barcode"),
            "inventory_quantity": v.get("inventoryQuantity"),
            "weight": v.get("weight"),
            "weight_unit": v.get("weightUnit"),
        }
        for v in (variants_data or [])
    ]

    # Transform options
    options_data = graphql_product.get("options", [])
    product["options"] = [
        {
            "id": from_gid(o.get("id", "")),
            "name": o.get("name"),
            "position": o.get("position"),
            "values": o.get("values", []),
        }
        for o in (options_data or [])
    ]

    # Transform images
    images_data = graphql_product.get("images", {})
    if isinstance(images_data, dict):
        images_data = images_data.get("nodes", []) or images_data.get("edges", [])
    if images_data and isinstance(images_data[0], dict) and "node" in images_data[0]:
        images_data = [e["node"] for e in images_data]

    product["images"] = [
        {
            "id": from_gid(img.get("id", "")),
            "src": img.get("url"),
            "alt": img.get("altText"),
        }
        for img in (images_data or [])
    ]

    return product


# GraphQL Queries and Mutations for Products
PRODUCTS_QUERY = """
query ListProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    edges {
      cursor
      node {
        id
        title
        handle
        descriptionHtml
        vendor
        productType
        status
        tags
        createdAt
        updatedAt
        totalInventory
        variants(first: 100) {
          nodes {
            id
            title
            price
            compareAtPrice
            sku
            barcode
            inventoryQuantity
            weight
            weightUnit
          }
        }
        options {
          id
          name
          position
          values
        }
        images(first: 20) {
          nodes {
            id
            url
            altText
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

PRODUCT_QUERY = """
query GetProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    descriptionHtml
    vendor
    productType
    status
    tags
    createdAt
    updatedAt
    totalInventory
    variants(first: 100) {
      nodes {
        id
        title
        price
        compareAtPrice
        sku
        barcode
        inventoryQuantity
        weight
        weightUnit
      }
    }
    options {
      id
      name
      position
      values
    }
    images(first: 20) {
      nodes {
        id
        url
        altText
      }
    }
  }
}
"""

PRODUCT_CREATE_MUTATION = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      descriptionHtml
      vendor
      productType
      status
      tags
      createdAt
      updatedAt
      variants(first: 100) {
        nodes {
          id
          title
          price
          sku
          inventoryQuantity
        }
      }
      options {
        id
        name
        position
        values
      }
      images(first: 20) {
        nodes {
          id
          url
          altText
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_UPDATE_MUTATION = """
mutation ProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      descriptionHtml
      vendor
      productType
      status
      tags
      createdAt
      updatedAt
      variants(first: 100) {
        nodes {
          id
          title
          price
          sku
          inventoryQuantity
        }
      }
      options {
        id
        name
        position
        values
      }
      images(first: 20) {
        nodes {
          id
          url
          altText
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""


# ============================================================================
# Customer Actions
# ============================================================================

@shopify_admin.action("list_customers")
class ListCustomersHandler(ActionHandler):
    """List customers with optional filtering and pagination."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/customers.json")
            headers = build_headers(context)

            allowed_params = [
                'limit', 'since_id', 'created_at_min', 'created_at_max',
                'updated_at_min', 'updated_at_max'
            ]
            params = build_query_params(inputs, allowed_params)

            if 'limit' not in params:
                params['limit'] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            customers = response.get('customers', [])
            return success_response(customers=customers, count=len(customers))
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("get_customer")
class GetCustomerHandler(ActionHandler):
    """Get a single customer by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_id = inputs['customer_id']
            url = get_api_url(context, f"/customers/{customer_id}.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(customer=response.get('customer', {}))
        except Exception as e:
            return error_response(e, customer=None)


@shopify_admin.action("search_customers")
class SearchCustomersHandler(ActionHandler):
    """Search customers by query string."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/customers/search.json")
            headers = build_headers(context)

            params = {'query': inputs['query']}
            if 'limit' in inputs and inputs['limit']:
                params['limit'] = inputs['limit']
            else:
                params['limit'] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            customers = response.get('customers', [])
            return success_response(customers=customers, count=len(customers))
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("create_customer")
class CreateCustomerHandler(ActionHandler):
    """Create a new customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/customers.json")
            headers = build_headers(context)

            customer_data = {}
            field_mapping = {
                'email': 'email',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'phone': 'phone',
                'verified_email': 'verified_email',
                'send_email_welcome': 'send_email_welcome',
                'tags': 'tags',
                'note': 'note',
                'tax_exempt': 'tax_exempt'
            }

            for input_field, api_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    customer_data[api_field] = inputs[input_field]

            if 'address' in inputs and inputs['address']:
                customer_data['addresses'] = [inputs['address']]

            payload = {"customer": customer_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(customer=response.get('customer', {}))
        except Exception as e:
            return error_response(e, customer=None)


@shopify_admin.action("update_customer")
class UpdateCustomerHandler(ActionHandler):
    """Update an existing customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_id = inputs['customer_id']
            url = get_api_url(context, f"/customers/{customer_id}.json")
            headers = build_headers(context)

            customer_data = {}
            field_mapping = {
                'email': 'email',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'phone': 'phone',
                'tags': 'tags',
                'note': 'note',
                'tax_exempt': 'tax_exempt'
            }

            for input_field, api_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    customer_data[api_field] = inputs[input_field]

            payload = {"customer": customer_data}
            response = await context.fetch(url, method="PUT", json=payload, headers=headers)

            return success_response(customer=response.get('customer', {}))
        except Exception as e:
            return error_response(e, customer=None)


# ============================================================================
# Order Actions
# ============================================================================

@shopify_admin.action("list_orders")
class ListOrdersHandler(ActionHandler):
    """List orders with optional filtering."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/orders.json")
            headers = build_headers(context)

            allowed_params = [
                'limit', 'status', 'financial_status', 'fulfillment_status',
                'since_id', 'created_at_min', 'created_at_max'
            ]
            params = build_query_params(inputs, allowed_params)

            if 'limit' not in params:
                params['limit'] = 50
            if 'status' not in params:
                params['status'] = 'any'

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            orders = response.get('orders', [])
            return success_response(orders=orders, count=len(orders))
        except Exception as e:
            return error_response(e, orders=[], count=0)


@shopify_admin.action("get_order")
class GetOrderHandler(ActionHandler):
    """Get a single order by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs['order_id']
            url = get_api_url(context, f"/orders/{order_id}.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(order=response.get('order', {}))
        except Exception as e:
            return error_response(e, order=None)


@shopify_admin.action("create_order")
class CreateOrderHandler(ActionHandler):
    """Create a new order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/orders.json")
            headers = build_headers(context)

            order_data = {"line_items": inputs['line_items']}

            optional_fields = [
                'customer_id', 'email', 'financial_status', 'fulfillment_status',
                'send_receipt', 'send_fulfillment_receipt', 'note', 'tags',
                'shipping_address', 'billing_address'
            ]

            for field in optional_fields:
                if field in inputs and inputs[field] is not None:
                    if field == 'customer_id':
                        order_data['customer'] = {'id': inputs[field]}
                    else:
                        order_data[field] = inputs[field]

            payload = {"order": order_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(order=response.get('order', {}))
        except Exception as e:
            return error_response(e, order=None)


@shopify_admin.action("cancel_order")
class CancelOrderHandler(ActionHandler):
    """Cancel an existing order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs['order_id']
            url = get_api_url(context, f"/orders/{order_id}/cancel.json")
            headers = build_headers(context)

            cancel_data = {}
            if 'reason' in inputs and inputs['reason']:
                cancel_data['reason'] = inputs['reason']
            if 'email' in inputs:
                cancel_data['email'] = inputs['email']
            if 'restock' in inputs:
                cancel_data['restock'] = inputs['restock']

            response = await context.fetch(url, method="POST", json=cancel_data, headers=headers)

            return success_response(order=response.get('order', {}))
        except Exception as e:
            return error_response(e, order=None)


# ============================================================================
# Product Actions (GraphQL)
# ============================================================================

@shopify_admin.action("list_products")
class ListProductsHandler(ActionHandler):
    """List products with optional filtering using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build variables for GraphQL query
            limit = inputs.get('limit', 50)
            if limit > 250:
                limit = 250  # GraphQL max is 250

            variables = {
                "first": limit,
                "after": inputs.get('after'),  # Cursor for pagination
                "query": build_product_query_filter(inputs)
            }

            # Remove None values
            variables = {k: v for k, v in variables.items() if v is not None}

            # Execute GraphQL query
            data = await execute_graphql(context, PRODUCTS_QUERY, variables)

            # Transform response
            products_data = data.get("products", {})
            edges = products_data.get("edges", [])
            page_info = products_data.get("pageInfo", {})

            products = [transform_product_response(edge["node"]) for edge in edges]

            return success_response(
                products=products,
                count=len(products),
                hasNextPage=page_info.get("hasNextPage", False),
                endCursor=page_info.get("endCursor")
            )
        except Exception as e:
            return error_response(e, products=[], count=0)


@shopify_admin.action("get_product")
class GetProductHandler(ActionHandler):
    """Get a single product by ID using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            product_id = inputs['product_id']
            # Convert to GID format if needed
            gid = to_gid("Product", product_id)

            variables = {"id": gid}

            # Execute GraphQL query
            data = await execute_graphql(context, PRODUCT_QUERY, variables)

            # Transform response
            product = transform_product_response(data.get("product", {}))

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product=None)


@shopify_admin.action("create_product")
class CreateProductHandler(ActionHandler):
    """Create a new product using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build GraphQL input
            product_input = {
                "title": inputs['title']
            }

            # Map REST field names to GraphQL field names
            if inputs.get('body_html'):
                product_input['descriptionHtml'] = inputs['body_html']
            if inputs.get('vendor'):
                product_input['vendor'] = inputs['vendor']
            if inputs.get('product_type'):
                product_input['productType'] = inputs['product_type']
            if inputs.get('tags'):
                # Convert comma-separated string to array if needed
                tags = inputs['tags']
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                product_input['tags'] = tags
            if inputs.get('status'):
                # Convert to uppercase for GraphQL enum
                product_input['status'] = inputs['status'].upper()

            # Handle variants - GraphQL uses different structure
            if inputs.get('variants'):
                variants = inputs['variants']
                graphql_variants = []
                for v in variants:
                    gql_variant = {}
                    if v.get('price'):
                        gql_variant['price'] = str(v['price'])
                    if v.get('sku'):
                        gql_variant['sku'] = v['sku']
                    if v.get('barcode'):
                        gql_variant['barcode'] = v['barcode']
                    if v.get('weight'):
                        gql_variant['weight'] = v['weight']
                    if v.get('compare_at_price'):
                        gql_variant['compareAtPrice'] = str(v['compare_at_price'])
                    if gql_variant:
                        graphql_variants.append(gql_variant)
                if graphql_variants:
                    product_input['variants'] = graphql_variants

            # Handle options - convert REST format to GraphQL productOptions format
            # REST format: [{"name": "Size", "values": ["S", "M"]}]
            # GraphQL format: [{name: "Size", values: [{name: "S"}, {name: "M"}]}]
            # Note: GraphQL uses 'productOptions' field, not 'options'
            if inputs.get('options'):
                options = inputs['options']
                graphql_options = []
                for opt in options:
                    if isinstance(opt, dict) and 'name' in opt:
                        graphql_opt = {'name': opt['name']}
                        # Convert values from strings to objects if needed
                        if opt.get('values'):
                            values = opt['values']
                            if values and isinstance(values[0], str):
                                # REST format: ["S", "M"] -> [{name: "S"}, {name: "M"}]
                                graphql_opt['values'] = [{'name': v} for v in values]
                            else:
                                # Already in GraphQL format
                                graphql_opt['values'] = values
                        graphql_options.append(graphql_opt)
                    elif isinstance(opt, str):
                        # Simple string option name
                        graphql_options.append({'name': opt})
                if graphql_options:
                    product_input['productOptions'] = graphql_options

            variables = {"input": product_input}

            # Execute GraphQL mutation
            data = await execute_graphql(context, PRODUCT_CREATE_MUTATION, variables)

            # Check for user errors
            result = data.get("productCreate", {})
            user_errors = result.get("userErrors", [])
            if user_errors:
                error_messages = [f"{e.get('field', 'unknown')}: {e.get('message', 'error')}" for e in user_errors]
                raise Exception(f"Product creation failed: {'; '.join(error_messages)}")

            # Transform response
            product = transform_product_response(result.get("product", {}))

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product=None)


@shopify_admin.action("update_product")
class UpdateProductHandler(ActionHandler):
    """Update an existing product using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            product_id = inputs['product_id']
            # Convert to GID format
            gid = to_gid("Product", product_id)

            # Build GraphQL input with product ID
            product_input = {"id": gid}

            # Map REST field names to GraphQL field names
            if inputs.get('title'):
                product_input['title'] = inputs['title']
            if inputs.get('body_html'):
                product_input['descriptionHtml'] = inputs['body_html']
            if inputs.get('vendor'):
                product_input['vendor'] = inputs['vendor']
            if inputs.get('product_type'):
                product_input['productType'] = inputs['product_type']
            if inputs.get('tags'):
                # Convert comma-separated string to array if needed
                tags = inputs['tags']
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                product_input['tags'] = tags
            if inputs.get('status'):
                # Convert to uppercase for GraphQL enum
                product_input['status'] = inputs['status'].upper()

            variables = {"input": product_input}

            # Execute GraphQL mutation
            data = await execute_graphql(context, PRODUCT_UPDATE_MUTATION, variables)

            # Check for user errors
            result = data.get("productUpdate", {})
            user_errors = result.get("userErrors", [])
            if user_errors:
                error_messages = [f"{e.get('field', 'unknown')}: {e.get('message', 'error')}" for e in user_errors]
                raise Exception(f"Product update failed: {'; '.join(error_messages)}")

            # Transform response
            product = transform_product_response(result.get("product", {}))

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product=None)


# ============================================================================
# Inventory Actions
# ============================================================================

@shopify_admin.action("get_inventory_levels")
class GetInventoryLevelsHandler(ActionHandler):
    """Get inventory levels by location or inventory item IDs."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/inventory_levels.json")
            headers = build_headers(context)

            params = {}
            if 'inventory_item_ids' in inputs and inputs['inventory_item_ids']:
                params['inventory_item_ids'] = inputs['inventory_item_ids']
            if 'location_ids' in inputs and inputs['location_ids']:
                params['location_ids'] = inputs['location_ids']
            if 'limit' in inputs and inputs['limit']:
                params['limit'] = inputs['limit']
            else:
                params['limit'] = 50

            if not params.get('inventory_item_ids') and not params.get('location_ids'):
                return error_response(
                    "Either inventory_item_ids or location_ids is required",
                    inventory_levels=[], count=0
                )

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            inventory_levels = response.get('inventory_levels', [])
            return success_response(inventory_levels=inventory_levels, count=len(inventory_levels))
        except Exception as e:
            return error_response(e, inventory_levels=[], count=0)


@shopify_admin.action("set_inventory_level")
class SetInventoryLevelHandler(ActionHandler):
    """Set inventory level for an item at a location."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/inventory_levels/set.json")
            headers = build_headers(context)

            payload = {
                "location_id": inputs['location_id'],
                "inventory_item_id": inputs['inventory_item_id'],
                "available": inputs['available']
            }

            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(inventory_level=response.get('inventory_level', {}))
        except Exception as e:
            return error_response(e, inventory_level=None)


# ============================================================================
# Location Actions
# ============================================================================

@shopify_admin.action("list_locations")
class ListLocationsHandler(ActionHandler):
    """List all store locations."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/locations.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            locations = response.get('locations', [])
            return success_response(locations=locations, count=len(locations))
        except Exception as e:
            return error_response(e, locations=[], count=0)


@shopify_admin.action("get_location")
class GetLocationHandler(ActionHandler):
    """Get a single location by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            location_id = inputs['location_id']
            url = get_api_url(context, f"/locations/{location_id}.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(location=response.get('location', {}))
        except Exception as e:
            return error_response(e, location=None)


# ============================================================================
# Shop Actions
# ============================================================================

@shopify_admin.action("get_shop")
class GetShopHandler(ActionHandler):
    """Get store information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/shop.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(shop=response.get('shop', {}))
        except Exception as e:
            return error_response(e, shop=None)


# ============================================================================
# Draft Order Actions
# ============================================================================

@shopify_admin.action("list_draft_orders")
class ListDraftOrdersHandler(ActionHandler):
    """List draft orders."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/draft_orders.json")
            headers = build_headers(context)

            allowed_params = ['limit', 'since_id', 'status']
            params = build_query_params(inputs, allowed_params)

            if 'limit' not in params:
                params['limit'] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            draft_orders = response.get('draft_orders', [])
            return success_response(draft_orders=draft_orders, count=len(draft_orders))
        except Exception as e:
            return error_response(e, draft_orders=[], count=0)


@shopify_admin.action("create_draft_order")
class CreateDraftOrderHandler(ActionHandler):
    """Create a new draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/draft_orders.json")
            headers = build_headers(context)

            draft_order_data = {"line_items": inputs['line_items']}

            optional_fields = [
                'customer_id', 'email', 'note', 'tags',
                'shipping_address', 'billing_address', 'use_customer_default_address'
            ]

            for field in optional_fields:
                if field in inputs and inputs[field] is not None:
                    if field == 'customer_id':
                        draft_order_data['customer'] = {'id': inputs[field]}
                    else:
                        draft_order_data[field] = inputs[field]

            payload = {"draft_order": draft_order_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(draft_order=response.get('draft_order', {}))
        except Exception as e:
            return error_response(e, draft_order=None)


@shopify_admin.action("complete_draft_order")
class CompleteDraftOrderHandler(ActionHandler):
    """Complete a draft order, converting it to a real order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_order_id = inputs['draft_order_id']
            url = get_api_url(context, f"/draft_orders/{draft_order_id}/complete.json")
            headers = build_headers(context)

            params = {}
            if 'payment_pending' in inputs:
                params['payment_pending'] = inputs['payment_pending']

            response = await context.fetch(url, method="PUT", params=params, headers=headers)

            return success_response(draft_order=response.get('draft_order', {}))
        except Exception as e:
            return error_response(e, draft_order=None)


@shopify_admin.action("delete_draft_order")
class DeleteDraftOrderHandler(ActionHandler):
    """Delete a draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_order_id = inputs['draft_order_id']
            url = get_api_url(context, f"/draft_orders/{draft_order_id}.json")
            headers = build_headers(context)

            await context.fetch(url, method="DELETE", headers=headers)

            return success_response(deleted=True, draft_order_id=draft_order_id)
        except Exception as e:
            return error_response(e, deleted=False)


# ============================================================================
# Fulfillment Actions
# ============================================================================

@shopify_admin.action("list_fulfillments")
class ListFulfillmentsHandler(ActionHandler):
    """List fulfillments for an order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs['order_id']
            url = get_api_url(context, f"/orders/{order_id}/fulfillments.json")
            headers = build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            fulfillments = response.get('fulfillments', [])
            return success_response(fulfillments=fulfillments, count=len(fulfillments))
        except Exception as e:
            return error_response(e, fulfillments=[], count=0)


@shopify_admin.action("create_fulfillment")
class CreateFulfillmentHandler(ActionHandler):
    """Create a fulfillment for an order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs['order_id']
            url = get_api_url(context, f"/orders/{order_id}/fulfillments.json")
            headers = build_headers(context)

            fulfillment_data = {
                "location_id": inputs['location_id']
            }

            optional_fields = [
                'tracking_number', 'tracking_company', 'tracking_url',
                'notify_customer', 'line_items'
            ]

            for field in optional_fields:
                if field in inputs and inputs[field] is not None:
                    fulfillment_data[field] = inputs[field]

            payload = {"fulfillment": fulfillment_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(fulfillment=response.get('fulfillment', {}))
        except Exception as e:
            return error_response(e, fulfillment=None)


@shopify_admin.action("update_fulfillment_tracking")
class UpdateFulfillmentTrackingHandler(ActionHandler):
    """Update tracking information for a fulfillment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            fulfillment_id = inputs['fulfillment_id']
            url = get_api_url(context, f"/fulfillments/{fulfillment_id}/update_tracking.json")
            headers = build_headers(context)

            tracking_data = {}
            if 'tracking_number' in inputs:
                tracking_data['number'] = inputs['tracking_number']
            if 'tracking_company' in inputs:
                tracking_data['company'] = inputs['tracking_company']
            if 'tracking_url' in inputs:
                tracking_data['url'] = inputs['tracking_url']

            payload = {
                "fulfillment": {
                    "tracking_info": tracking_data,
                    "notify_customer": inputs.get('notify_customer', False)
                }
            }

            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(fulfillment=response.get('fulfillment', {}))
        except Exception as e:
            return error_response(e, fulfillment=None)
