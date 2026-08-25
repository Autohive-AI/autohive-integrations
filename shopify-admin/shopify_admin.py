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
- Merchant-provided Shopify app client ID and secret
- OAuth 2.0 client credentials grant
- Header: X-Shopify-Access-Token

Rate Limits:
- GraphQL: 100 points/second (1,000 capacity)
- REST: 40 requests/minute

API Version: 2026-07
"""

from autohive_integrations_sdk import (
    ActionError,
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
import re
from typing import Dict, Any

# Create the integration using the config.json
shopify_admin = Integration.load()

# Shopify API version
API_VERSION = "2026-07"
SHOP_DOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$", re.IGNORECASE)
WEIGHT_UNIT_ALIASES = {
    "G": "GRAMS",
    "GRAM": "GRAMS",
    "GRAMS": "GRAMS",
    "KG": "KILOGRAMS",
    "KILOGRAM": "KILOGRAMS",
    "KILOGRAMS": "KILOGRAMS",
    "LB": "POUNDS",
    "LBS": "POUNDS",
    "POUND": "POUNDS",
    "POUNDS": "POUNDS",
    "OZ": "OUNCES",
    "OUNCE": "OUNCES",
    "OUNCES": "OUNCES",
}


# ============================================================================
# Helper Functions
# ============================================================================


def get_credentials(context: ExecutionContext) -> Dict[str, Any]:
    """Return custom auth fields from the platform auth envelope."""
    credentials = context.auth.get("credentials", {})
    return credentials if isinstance(credentials, dict) else {}


def get_shop_url(context: ExecutionContext) -> str:
    """Return and validate the store's permanent myshopify.com domain."""
    shop_url = str(get_credentials(context).get("shop_url", "")).strip().lower()
    if shop_url.startswith("https://"):
        shop_url = shop_url[len("https://") :]
    elif shop_url.startswith("http://"):
        shop_url = shop_url[len("http://") :]
    shop_url = shop_url.rstrip("/")

    if not SHOP_DOMAIN_PATTERN.fullmatch(shop_url):
        raise ValueError("Shop domain must use the format your-store.myshopify.com")
    return shop_url


def get_api_url(context: ExecutionContext, endpoint: str = "") -> str:
    """Build Shopify Admin API URL."""
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/admin/api/{API_VERSION}{endpoint}"


async def get_access_token(context: ExecutionContext) -> str:
    """Exchange the merchant's app credentials for a short-lived access token."""
    credentials = get_credentials(context)
    client_id = str(credentials.get("client_id", "")).strip()
    client_secret = str(credentials.get("client_secret", "")).strip()
    missing = [name for name, value in (("client_id", client_id), ("client_secret", client_secret)) if not value]
    if missing:
        raise ValueError(f"Missing Shopify credential: {', '.join(missing)}")

    response = await context.fetch(
        f"https://{get_shop_url(context)}/admin/oauth/access_token",
        method="POST",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        content_type="application/x-www-form-urlencoded",
    )
    token_data = response.data
    access_token = token_data.get("access_token") if isinstance(token_data, dict) else None
    if not access_token:
        raise ValueError("Shopify did not return an access token")
    return access_token


async def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build Shopify API headers using a freshly acquired access token."""
    access_token = await get_access_token(context)
    return {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}


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


def error_response(message: str, **_kwargs) -> ActionError:
    """Build a standardized action error."""
    return ActionError(message=str(message))


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
    headers = await build_headers(context)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = await context.fetch(url, method="POST", json=payload, headers=headers)
    response_data = response.data

    # Check for GraphQL errors
    if "errors" in response_data:
        error_messages = [e.get("message", str(e)) for e in response_data["errors"]]
        raise Exception(f"GraphQL Error: {'; '.join(error_messages)}")

    return response_data.get("data", {})


def escape_graphql_query_value(value: str) -> str:
    """Escape and quote a value for use in GraphQL query filter strings.

    Values containing spaces or special characters need to be quoted.
    Double quotes within the value are escaped with backslash.
    """
    value = str(value)
    # Escape backslashes first, then double quotes
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    # Always quote the value to handle spaces and special characters safely
    return f'"{escaped}"'


def build_product_query_filter(inputs: Dict[str, Any]) -> str:
    """Build GraphQL query filter string from inputs."""
    filters = []

    if inputs.get("title"):
        # For wildcard search with spaces, format is: title:*"value"*
        title = str(inputs["title"]).replace("\\", "\\\\").replace('"', '\\"')
        filters.append(f'title:*"{title}"*')
    if inputs.get("vendor"):
        filters.append(f"vendor:{escape_graphql_query_value(inputs['vendor'])}")
    if inputs.get("product_type"):
        filters.append(f"product_type:{escape_graphql_query_value(inputs['product_type'])}")
    if inputs.get("status"):
        filters.append(f"status:{inputs['status']}")
    if inputs.get("created_at_min"):
        filters.append(f"created_at:>{inputs['created_at_min']}")
    if inputs.get("created_at_max"):
        filters.append(f"created_at:<{inputs['created_at_max']}")

    return " AND ".join(filters) if filters else None


def transform_variant_response(graphql_variant: dict) -> dict:
    """Transform a GraphQL product variant to the integration's response shape."""
    inventory_item = graphql_variant.get("inventoryItem") or {}
    measurement = inventory_item.get("measurement") or {}
    weight = measurement.get("weight") or {}
    return {
        "id": from_gid(graphql_variant.get("id", "")),
        "title": graphql_variant.get("title"),
        "price": graphql_variant.get("price"),
        "compare_at_price": graphql_variant.get("compareAtPrice"),
        "sku": graphql_variant.get("sku"),
        "barcode": graphql_variant.get("barcode"),
        "inventory_quantity": graphql_variant.get("inventoryQuantity"),
        "weight": weight.get("value"),
        "weight_unit": weight.get("unit"),
    }


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
        "tags": ", ".join(graphql_product.get("tags", []))
        if isinstance(graphql_product.get("tags"), list)
        else graphql_product.get("tags", ""),
        "created_at": graphql_product.get("createdAt"),
        "updated_at": graphql_product.get("updatedAt"),
    }

    # Transform variants
    variants_data = graphql_product.get("variants", {})
    if isinstance(variants_data, dict):
        variants_data = variants_data.get("nodes", []) or variants_data.get("edges", [])
    if variants_data and isinstance(variants_data[0], dict) and "node" in variants_data[0]:
        variants_data = [e["node"] for e in variants_data]

    product["variants"] = [transform_variant_response(variant) for variant in (variants_data or [])]

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


def normalize_weight_unit(value: str) -> str:
    """Return a Shopify WeightUnit value, accepting common abbreviations."""
    normalized = str(value or "GRAMS").strip().upper()
    if normalized not in WEIGHT_UNIT_ALIASES:
        valid_units = ", ".join(sorted({"GRAMS", "KILOGRAMS", "OUNCES", "POUNDS"}))
        raise ValueError(f"Unsupported weight_unit '{value}'. Use one of: {valid_units}")
    return WEIGHT_UNIT_ALIASES[normalized]


def build_variant_option_values(variant: dict, product_options: list) -> list:
    """Convert supported variant option formats to VariantOptionValueInput objects."""
    option_values = variant.get("option_values", variant.get("optionValues"))
    if isinstance(option_values, dict):
        return [{"optionName": option_name, "name": name} for option_name, name in option_values.items()]

    if option_values:
        graphql_values = []
        key_mapping = {
            "option_name": "optionName",
            "option_id": "optionId",
            "linked_metafield_value": "linkedMetafieldValue",
        }
        allowed_fields = {"id", "name", "optionId", "optionName", "linkedMetafieldValue"}
        for option_value in option_values:
            if not isinstance(option_value, dict):
                raise ValueError("Each variant option_values entry must be an object")
            normalized_value = {key_mapping.get(key, key): value for key, value in option_value.items()}
            graphql_value = {key: value for key, value in normalized_value.items() if key in allowed_fields}
            if not graphql_value:
                raise ValueError("Each variant option_values entry must identify an option and value")
            graphql_values.append(graphql_value)
        return graphql_values

    graphql_values = []
    for index, option in enumerate(product_options, start=1):
        option_name = option.get("name") if isinstance(option, dict) else option
        option_value = variant.get(f"option{index}")
        if option_name and option_value is not None:
            graphql_values.append({"optionName": option_name, "name": str(option_value)})
    return graphql_values


def build_product_variant_input(variant: dict, product_options: list) -> dict:
    """Build a ProductVariantsBulkInput for Shopify Admin API 2026-07."""
    if not isinstance(variant, dict):
        raise ValueError("Each product variant must be an object")

    graphql_variant = {}
    if variant.get("price") is not None:
        graphql_variant["price"] = str(variant["price"])
    if variant.get("compare_at_price") is not None:
        graphql_variant["compareAtPrice"] = str(variant["compare_at_price"])
    if variant.get("barcode") is not None:
        graphql_variant["barcode"] = variant["barcode"]

    inventory_item = {}
    if variant.get("sku") is not None:
        inventory_item["sku"] = variant["sku"]
    if variant.get("weight") is not None:
        inventory_item["measurement"] = {
            "weight": {
                "value": float(variant["weight"]),
                "unit": normalize_weight_unit(variant.get("weight_unit", "GRAMS")),
            }
        }
    if inventory_item:
        graphql_variant["inventoryItem"] = inventory_item

    option_values = build_variant_option_values(variant, product_options)
    if option_values:
        graphql_variant["optionValues"] = option_values
    return graphql_variant


def format_graphql_user_errors(operation: str, user_errors: list) -> str:
    """Format Shopify mutation user errors into an actionable exception message."""
    messages = [f"{error.get('field', 'unknown')}: {error.get('message', 'error')}" for error in user_errors]
    return f"{operation} failed: {'; '.join(messages)}"


def build_fulfillment_order_payload(fulfillment_orders: list, location_id: str, requested_line_items: list) -> list:
    """Map order line items to Shopify's fulfillment-order based request shape."""
    eligible_orders = []
    for fulfillment_order in fulfillment_orders:
        supported_actions = fulfillment_order.get("supported_actions") or []
        if str(fulfillment_order.get("assigned_location_id")) != str(location_id):
            continue
        if supported_actions and "create_fulfillment" not in supported_actions:
            continue
        eligible_orders.append(fulfillment_order)

    if not eligible_orders:
        raise ValueError(f"No fulfillable fulfillment orders were found at location {location_id}")

    if not requested_line_items:
        return [{"fulfillment_order_id": fulfillment_order["id"]} for fulfillment_order in eligible_orders]

    requested_by_id = {}
    for line_item in requested_line_items:
        if not isinstance(line_item, dict) or line_item.get("id") is None:
            raise ValueError("Each line_items entry must include an order line item id")
        requested_by_id[str(line_item["id"])] = line_item

    matched_ids = set()
    line_items_by_fulfillment_order = []
    for fulfillment_order in eligible_orders:
        fulfillment_order_line_items = []
        for fulfillment_order_line_item in fulfillment_order.get("line_items", []):
            candidate_ids = {
                str(fulfillment_order_line_item.get("id")),
                str(fulfillment_order_line_item.get("line_item_id")),
            }
            requested_id = next((item_id for item_id in candidate_ids if item_id in requested_by_id), None)
            if requested_id is None:
                continue
            requested = requested_by_id[requested_id]
            quantity = requested.get("quantity", fulfillment_order_line_item.get("fulfillable_quantity"))
            if quantity is None:
                quantity = fulfillment_order_line_item.get("quantity")
            fulfillment_order_line_items.append(
                {
                    "id": fulfillment_order_line_item["id"],
                    "quantity": quantity,
                }
            )
            matched_ids.add(requested_id)

        if fulfillment_order_line_items:
            line_items_by_fulfillment_order.append(
                {
                    "fulfillment_order_id": fulfillment_order["id"],
                    "fulfillment_order_line_items": fulfillment_order_line_items,
                }
            )

    unmatched_ids = set(requested_by_id) - matched_ids
    if unmatched_ids:
        raise ValueError(f"Line items not fulfillable at location {location_id}: {', '.join(sorted(unmatched_ids))}")
    return line_items_by_fulfillment_order


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
            inventoryItem {
              measurement {
                weight {
                  value
                  unit
                }
              }
            }
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
        inventoryItem {
          measurement {
            weight {
              value
              unit
            }
          }
        }
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
mutation ProductCreate($product: ProductCreateInput!) {
  productCreate(product: $product) {
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
mutation ProductUpdate($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
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

PRODUCT_VARIANTS_BULK_CREATE_MUTATION = """
mutation ProductVariantsBulkCreate(
  $productId: ID!
  $variants: [ProductVariantsBulkInput!]!
  $strategy: ProductVariantsBulkCreateStrategy
) {
  productVariantsBulkCreate(productId: $productId, variants: $variants, strategy: $strategy) {
    productVariants {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_VARIANTS_BULK_UPDATE_MUTATION = """
mutation ProductVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
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
            headers = await build_headers(context)

            allowed_params = [
                "limit",
                "since_id",
                "created_at_min",
                "created_at_max",
                "updated_at_min",
                "updated_at_max",
            ]
            params = build_query_params(inputs, allowed_params)

            if "limit" not in params:
                params["limit"] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            customers = response.data.get("customers", [])
            return success_response(customers=customers, count=len(customers))
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("get_customer")
class GetCustomerHandler(ActionHandler):
    """Get a single customer by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_id = inputs["customer_id"]
            url = get_api_url(context, f"/customers/{customer_id}.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(customer=response.data.get("customer", {}))
        except Exception as e:
            return error_response(e, customer={})


@shopify_admin.action("search_customers")
class SearchCustomersHandler(ActionHandler):
    """Search customers by query string."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/customers/search.json")
            headers = await build_headers(context)

            params = {"query": inputs["query"]}
            if "limit" in inputs and inputs["limit"]:
                params["limit"] = inputs["limit"]
            else:
                params["limit"] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            customers = response.data.get("customers", [])
            return success_response(customers=customers, count=len(customers))
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("create_customer")
class CreateCustomerHandler(ActionHandler):
    """Create a new customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/customers.json")
            headers = await build_headers(context)

            customer_data = {}
            field_mapping = {
                "email": "email",
                "first_name": "first_name",
                "last_name": "last_name",
                "phone": "phone",
                "verified_email": "verified_email",
                "send_email_welcome": "send_email_welcome",
                "tags": "tags",
                "note": "note",
                "tax_exempt": "tax_exempt",
            }

            for input_field, api_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    customer_data[api_field] = inputs[input_field]

            if "address" in inputs and inputs["address"]:
                customer_data["addresses"] = [inputs["address"]]

            payload = {"customer": customer_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(customer=response.data.get("customer", {}))
        except Exception as e:
            return error_response(e, customer={})


@shopify_admin.action("update_customer")
class UpdateCustomerHandler(ActionHandler):
    """Update an existing customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_id = inputs["customer_id"]
            url = get_api_url(context, f"/customers/{customer_id}.json")
            headers = await build_headers(context)

            customer_data = {}
            field_mapping = {
                "email": "email",
                "first_name": "first_name",
                "last_name": "last_name",
                "phone": "phone",
                "tags": "tags",
                "note": "note",
                "tax_exempt": "tax_exempt",
            }

            for input_field, api_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    customer_data[api_field] = inputs[input_field]

            payload = {"customer": customer_data}
            response = await context.fetch(url, method="PUT", json=payload, headers=headers)

            return success_response(customer=response.data.get("customer", {}))
        except Exception as e:
            return error_response(e, customer={})


# ============================================================================
# Order Actions
# ============================================================================


@shopify_admin.action("list_orders")
class ListOrdersHandler(ActionHandler):
    """List orders with optional filtering."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/orders.json")
            headers = await build_headers(context)

            allowed_params = [
                "limit",
                "status",
                "financial_status",
                "fulfillment_status",
                "since_id",
                "created_at_min",
                "created_at_max",
            ]
            params = build_query_params(inputs, allowed_params)

            if "limit" not in params:
                params["limit"] = 50
            if "status" not in params:
                params["status"] = "any"

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            orders = response.data.get("orders", [])
            return success_response(orders=orders, count=len(orders))
        except Exception as e:
            return error_response(e, orders=[], count=0)


@shopify_admin.action("get_order")
class GetOrderHandler(ActionHandler):
    """Get a single order by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs["order_id"]
            url = get_api_url(context, f"/orders/{order_id}.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(order=response.data.get("order", {}))
        except Exception as e:
            return error_response(e, order={})


@shopify_admin.action("create_order")
class CreateOrderHandler(ActionHandler):
    """Create a new order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/orders.json")
            headers = await build_headers(context)

            order_data = {"line_items": inputs["line_items"]}

            optional_fields = [
                "customer_id",
                "email",
                "financial_status",
                "fulfillment_status",
                "send_receipt",
                "send_fulfillment_receipt",
                "note",
                "tags",
                "shipping_address",
                "billing_address",
            ]

            for field in optional_fields:
                if field in inputs and inputs[field] is not None:
                    if field == "customer_id":
                        order_data["customer"] = {"id": inputs[field]}
                    else:
                        order_data[field] = inputs[field]

            payload = {"order": order_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(order=response.data.get("order", {}))
        except Exception as e:
            return error_response(e, order={})


@shopify_admin.action("cancel_order")
class CancelOrderHandler(ActionHandler):
    """Cancel an existing order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs["order_id"]
            url = get_api_url(context, f"/orders/{order_id}/cancel.json")
            headers = await build_headers(context)

            cancel_data = {}
            if "reason" in inputs and inputs["reason"]:
                cancel_data["reason"] = inputs["reason"]
            if "email" in inputs:
                cancel_data["email"] = inputs["email"]
            if "restock" in inputs:
                cancel_data["restock"] = inputs["restock"]

            response = await context.fetch(url, method="POST", json=cancel_data, headers=headers)

            return success_response(order=response.data.get("order", {}))
        except Exception as e:
            return error_response(e, order={})


# ============================================================================
# Product Actions (GraphQL)
# ============================================================================


@shopify_admin.action("list_products")
class ListProductsHandler(ActionHandler):
    """List products with optional filtering using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build variables for GraphQL query
            limit = inputs.get("limit", 50)
            if limit > 250:
                limit = 250  # GraphQL max is 250

            variables = {
                "first": limit,
                "after": inputs.get("after"),  # Cursor for pagination
                "query": build_product_query_filter(inputs),
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

            result_data = {
                "products": products,
                "count": len(products),
                "hasNextPage": page_info.get("hasNextPage", False),
            }
            if page_info.get("endCursor") is not None:
                result_data["endCursor"] = page_info["endCursor"]

            return success_response(**result_data)
        except Exception as e:
            return error_response(e, products=[], count=0)


@shopify_admin.action("get_product")
class GetProductHandler(ActionHandler):
    """Get a single product by ID using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            product_id = inputs["product_id"]
            # Convert to GID format if needed
            gid = to_gid("Product", product_id)

            variables = {"id": gid}

            # Execute GraphQL query
            data = await execute_graphql(context, PRODUCT_QUERY, variables)

            # Transform response
            product = transform_product_response(data.get("product", {}))

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product={})


@shopify_admin.action("create_product")
class CreateProductHandler(ActionHandler):
    """Create a new product using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build GraphQL input
            product_input = {"title": inputs["title"]}
            variants = inputs.get("variants") or []
            options = inputs.get("options") or []

            # Map REST field names to GraphQL field names
            if inputs.get("body_html"):
                product_input["descriptionHtml"] = inputs["body_html"]
            if inputs.get("vendor"):
                product_input["vendor"] = inputs["vendor"]
            if inputs.get("product_type"):
                product_input["productType"] = inputs["product_type"]
            if inputs.get("tags"):
                # Convert comma-separated string to array if needed
                tags = inputs["tags"]
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                product_input["tags"] = tags
            if inputs.get("status"):
                # Convert to uppercase for GraphQL enum
                product_input["status"] = inputs["status"].upper()

            # Handle options - convert REST format to GraphQL productOptions format
            # REST format: [{"name": "Size", "values": ["S", "M"]}]
            # GraphQL format: [{name: "Size", values: [{name: "S"}, {name: "M"}]}]
            # Note: GraphQL uses 'productOptions' field, not 'options'
            if options:
                graphql_options = []
                for opt in options:
                    if isinstance(opt, dict) and "name" in opt:
                        graphql_opt = {"name": opt["name"]}
                        # Convert values from strings to objects if needed
                        if opt.get("values"):
                            values = opt["values"]
                            if values and isinstance(values[0], str):
                                # REST format: ["S", "M"] -> [{name: "S"}, {name: "M"}]
                                graphql_opt["values"] = [{"name": v} for v in values]
                            else:
                                # Already in GraphQL format
                                graphql_opt["values"] = values
                        graphql_options.append(graphql_opt)
                    elif isinstance(opt, str):
                        # Simple string option name
                        graphql_options.append({"name": opt})
                if graphql_options:
                    product_input["productOptions"] = graphql_options

            graphql_variants = [build_product_variant_input(variant, options) for variant in variants]
            has_option_values = [bool(variant.get("optionValues")) for variant in graphql_variants]
            if len(graphql_variants) > 1 and not all(has_option_values):
                raise ValueError("Each of multiple product variants must provide option_values")

            variables = {"product": product_input}

            # Execute GraphQL mutation
            data = await execute_graphql(context, PRODUCT_CREATE_MUTATION, variables)

            # Check for user errors
            result = data.get("productCreate", {})
            user_errors = result.get("userErrors", [])
            if user_errors:
                raise Exception(format_graphql_user_errors("Product creation", user_errors))

            graphql_product = result.get("product") or {}
            product_id = graphql_product.get("id")
            if not product_id:
                raise Exception("Product creation failed: Shopify did not return a product ID")

            if graphql_variants:
                if len(graphql_variants) == 1 and not has_option_values[0]:
                    standalone_variants = (graphql_product.get("variants") or {}).get("nodes", [])
                    if not standalone_variants:
                        raise Exception(
                            f"Product {product_id} was created, but its standalone variant was not returned"
                        )
                    graphql_variants[0]["id"] = standalone_variants[0]["id"]
                    variant_data = await execute_graphql(
                        context,
                        PRODUCT_VARIANTS_BULK_UPDATE_MUTATION,
                        {"productId": product_id, "variants": graphql_variants},
                    )
                    variant_result = variant_data.get("productVariantsBulkUpdate", {})
                    variant_operation = "Product variant update"
                else:
                    variant_data = await execute_graphql(
                        context,
                        PRODUCT_VARIANTS_BULK_CREATE_MUTATION,
                        {
                            "productId": product_id,
                            "variants": graphql_variants,
                            "strategy": "REMOVE_STANDALONE_VARIANT",
                        },
                    )
                    variant_result = variant_data.get("productVariantsBulkCreate", {})
                    variant_operation = "Product variant creation"

                variant_errors = variant_result.get("userErrors", [])
                if variant_errors:
                    raise Exception(
                        f"Product {product_id} was created, but "
                        f"{format_graphql_user_errors(variant_operation, variant_errors).lower()}"
                    )

                product_data = await execute_graphql(context, PRODUCT_QUERY, {"id": product_id})
                graphql_product = product_data.get("product") or {}

            # Transform response
            product = transform_product_response(graphql_product)

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product={})


@shopify_admin.action("update_product")
class UpdateProductHandler(ActionHandler):
    """Update an existing product using GraphQL API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            product_id = inputs["product_id"]
            # Convert to GID format
            gid = to_gid("Product", product_id)

            # Build GraphQL input with product ID
            product_input = {"id": gid}

            # Map REST field names to GraphQL field names
            if inputs.get("title"):
                product_input["title"] = inputs["title"]
            if inputs.get("body_html"):
                product_input["descriptionHtml"] = inputs["body_html"]
            if inputs.get("vendor"):
                product_input["vendor"] = inputs["vendor"]
            if inputs.get("product_type"):
                product_input["productType"] = inputs["product_type"]
            if inputs.get("tags"):
                # Convert comma-separated string to array if needed
                tags = inputs["tags"]
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                product_input["tags"] = tags
            if inputs.get("status"):
                # Convert to uppercase for GraphQL enum
                product_input["status"] = inputs["status"].upper()

            variables = {"product": product_input}

            # Execute GraphQL mutation
            data = await execute_graphql(context, PRODUCT_UPDATE_MUTATION, variables)

            # Check for user errors
            result = data.get("productUpdate", {})
            user_errors = result.get("userErrors", [])
            if user_errors:
                raise Exception(format_graphql_user_errors("Product update", user_errors))

            # Transform response
            product = transform_product_response(result.get("product", {}))

            return success_response(product=product)
        except Exception as e:
            return error_response(e, product={})


# ============================================================================
# Inventory Actions
# ============================================================================


@shopify_admin.action("get_inventory_levels")
class GetInventoryLevelsHandler(ActionHandler):
    """Get inventory levels by location or inventory item IDs."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/inventory_levels.json")
            headers = await build_headers(context)

            params = {}
            if "inventory_item_ids" in inputs and inputs["inventory_item_ids"]:
                params["inventory_item_ids"] = inputs["inventory_item_ids"]
            if "location_ids" in inputs and inputs["location_ids"]:
                params["location_ids"] = inputs["location_ids"]
            if "limit" in inputs and inputs["limit"]:
                params["limit"] = inputs["limit"]
            else:
                params["limit"] = 50

            if not params.get("inventory_item_ids") and not params.get("location_ids"):
                return error_response(
                    "Either inventory_item_ids or location_ids is required",
                    inventory_levels=[],
                    count=0,
                )

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            inventory_levels = response.data.get("inventory_levels", [])
            return success_response(inventory_levels=inventory_levels, count=len(inventory_levels))
        except Exception as e:
            return error_response(e, inventory_levels=[], count=0)


@shopify_admin.action("set_inventory_level")
class SetInventoryLevelHandler(ActionHandler):
    """Set inventory level for an item at a location."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/inventory_levels/set.json")
            headers = await build_headers(context)

            payload = {
                "location_id": inputs["location_id"],
                "inventory_item_id": inputs["inventory_item_id"],
                "available": inputs["available"],
            }

            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(inventory_level=response.data.get("inventory_level", {}))
        except Exception as e:
            return error_response(e, inventory_level={})


# ============================================================================
# Location Actions
# ============================================================================


@shopify_admin.action("list_locations")
class ListLocationsHandler(ActionHandler):
    """List all store locations."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/locations.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            locations = response.data.get("locations", [])
            return success_response(locations=locations, count=len(locations))
        except Exception as e:
            return error_response(e, locations=[], count=0)


@shopify_admin.action("get_location")
class GetLocationHandler(ActionHandler):
    """Get a single location by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            location_id = inputs["location_id"]
            url = get_api_url(context, f"/locations/{location_id}.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(location=response.data.get("location", {}))
        except Exception as e:
            return error_response(e, location={})


# ============================================================================
# Shop Actions
# ============================================================================


@shopify_admin.action("get_shop")
class GetShopHandler(ActionHandler):
    """Get store information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/shop.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            return success_response(shop=response.data.get("shop", {}))
        except Exception as e:
            return error_response(e, shop={})


# ============================================================================
# Draft Order Actions
# ============================================================================


@shopify_admin.action("list_draft_orders")
class ListDraftOrdersHandler(ActionHandler):
    """List draft orders."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/draft_orders.json")
            headers = await build_headers(context)

            allowed_params = ["limit", "since_id", "status"]
            params = build_query_params(inputs, allowed_params)

            if "limit" not in params:
                params["limit"] = 50

            response = await context.fetch(url, method="GET", params=params, headers=headers)

            draft_orders = response.data.get("draft_orders", [])
            return success_response(draft_orders=draft_orders, count=len(draft_orders))
        except Exception as e:
            return error_response(e, draft_orders=[], count=0)


@shopify_admin.action("create_draft_order")
class CreateDraftOrderHandler(ActionHandler):
    """Create a new draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            url = get_api_url(context, "/draft_orders.json")
            headers = await build_headers(context)

            draft_order_data = {"line_items": inputs["line_items"]}

            optional_fields = [
                "customer_id",
                "email",
                "note",
                "tags",
                "shipping_address",
                "billing_address",
                "use_customer_default_address",
            ]

            for field in optional_fields:
                if field in inputs and inputs[field] is not None:
                    if field == "customer_id":
                        draft_order_data["customer"] = {"id": inputs[field]}
                    else:
                        draft_order_data[field] = inputs[field]

            payload = {"draft_order": draft_order_data}
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(draft_order=response.data.get("draft_order", {}))
        except Exception as e:
            return error_response(e, draft_order={})


@shopify_admin.action("complete_draft_order")
class CompleteDraftOrderHandler(ActionHandler):
    """Complete a draft order, converting it to a real order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_order_id = inputs["draft_order_id"]
            url = get_api_url(context, f"/draft_orders/{draft_order_id}/complete.json")
            headers = await build_headers(context)

            params = {}
            if "payment_pending" in inputs:
                params["payment_pending"] = inputs["payment_pending"]

            response = await context.fetch(url, method="PUT", params=params, headers=headers)

            return success_response(draft_order=response.data.get("draft_order", {}))
        except Exception as e:
            return error_response(e, draft_order={})


@shopify_admin.action("delete_draft_order")
class DeleteDraftOrderHandler(ActionHandler):
    """Delete a draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_order_id = inputs["draft_order_id"]
            url = get_api_url(context, f"/draft_orders/{draft_order_id}.json")
            headers = await build_headers(context)

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
            order_id = inputs["order_id"]
            url = get_api_url(context, f"/orders/{order_id}/fulfillments.json")
            headers = await build_headers(context)

            response = await context.fetch(url, method="GET", headers=headers)

            fulfillments = response.data.get("fulfillments", [])
            return success_response(fulfillments=fulfillments, count=len(fulfillments))
        except Exception as e:
            return error_response(e, fulfillments=[], count=0)


@shopify_admin.action("create_fulfillment")
class CreateFulfillmentHandler(ActionHandler):
    """Create a fulfillment for an order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs["order_id"]
            headers = await build_headers(context)

            fulfillment_orders_url = get_api_url(context, f"/orders/{order_id}/fulfillment_orders.json")
            fulfillment_orders_response = await context.fetch(
                fulfillment_orders_url,
                method="GET",
                headers=headers,
            )
            fulfillment_orders = fulfillment_orders_response.data.get("fulfillment_orders", [])
            line_items_by_fulfillment_order = build_fulfillment_order_payload(
                fulfillment_orders,
                inputs["location_id"],
                inputs.get("line_items") or [],
            )

            fulfillment_data = {
                "line_items_by_fulfillment_order": line_items_by_fulfillment_order,
                "notify_customer": inputs.get("notify_customer", True),
            }
            tracking_info = {}
            if inputs.get("tracking_number"):
                tracking_info["number"] = inputs["tracking_number"]
            if inputs.get("tracking_company"):
                tracking_info["company"] = inputs["tracking_company"]
            if inputs.get("tracking_url"):
                tracking_info["url"] = inputs["tracking_url"]
            if tracking_info:
                fulfillment_data["tracking_info"] = tracking_info

            payload = {"fulfillment": fulfillment_data}
            url = get_api_url(context, "/fulfillments.json")
            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(fulfillment=response.data.get("fulfillment", {}))
        except Exception as e:
            return error_response(e, fulfillment={})


@shopify_admin.action("update_fulfillment_tracking")
class UpdateFulfillmentTrackingHandler(ActionHandler):
    """Update tracking information for a fulfillment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            fulfillment_id = inputs["fulfillment_id"]
            url = get_api_url(context, f"/fulfillments/{fulfillment_id}/update_tracking.json")
            headers = await build_headers(context)

            tracking_data = {}
            if "tracking_number" in inputs:
                tracking_data["number"] = inputs["tracking_number"]
            if "tracking_company" in inputs:
                tracking_data["company"] = inputs["tracking_company"]
            if "tracking_url" in inputs:
                tracking_data["url"] = inputs["tracking_url"]

            payload = {
                "fulfillment": {
                    "tracking_info": tracking_data,
                    "notify_customer": inputs.get("notify_customer", False),
                }
            }

            response = await context.fetch(url, method="POST", json=payload, headers=headers)

            return success_response(fulfillment=response.data.get("fulfillment", {}))
        except Exception as e:
            return error_response(e, fulfillment={})
