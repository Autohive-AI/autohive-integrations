"""
Shopify Admin API Integration
=============================

Provides access to Shopify's GraphQL Admin API for store management operations.

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
from time import monotonic
from uuid import uuid4
from typing import Dict, Any

# Create the integration using the config.json
shopify_admin = Integration.load()

# Shopify API version
API_VERSION = "2026-07"
SHOP_DOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$", re.IGNORECASE)
TOKEN_EXPIRY_SKEW_SECONDS = 60
AUTH_CACHE_ATTRIBUTE = "_shopify_admin_auth_cache"
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


async def get_access_token(context: ExecutionContext) -> str:
    """Return a cached access token or exchange the app credentials for one."""
    credentials = get_credentials(context)
    client_id = str(credentials.get("client_id", "")).strip()
    client_secret = str(credentials.get("client_secret", "")).strip()
    missing = [name for name, value in (("client_id", client_id), ("client_secret", client_secret)) if not value]
    if missing:
        raise ValueError(f"Missing Shopify credential: {', '.join(missing)}")

    shop_url = get_shop_url(context)
    credential_key = (shop_url, client_id, client_secret)
    now = monotonic()
    token_cache = context.__dict__.get(AUTH_CACHE_ATTRIBUTE)
    if (
        isinstance(token_cache, dict)
        and token_cache.get("credential_key") == credential_key
        and token_cache.get("expires_at", 0) > now
        and token_cache.get("access_token")
    ):
        return token_cache["access_token"]

    response = await context.fetch(
        f"https://{shop_url}/admin/oauth/access_token",
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

    try:
        expires_in = float(token_data.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0
    cache_lifetime = max(0, expires_in - TOKEN_EXPIRY_SKEW_SECONDS)
    if cache_lifetime:
        setattr(
            context,
            AUTH_CACHE_ATTRIBUTE,
            {
                "access_token": access_token,
                "credential_key": credential_key,
                "expires_at": now + cache_lifetime,
            },
        )
    return access_token


async def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build Shopify API headers using a freshly acquired access token."""
    access_token = await get_access_token(context)
    return {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}


def success_response(**kwargs) -> ActionResult:
    """Build a standardized success response."""
    return ActionResult(data={"success": True, **kwargs}, cost_usd=0)


def partial_success_response(message: str, **kwargs) -> ActionResult:
    """Report a completed primary mutation followed by a secondary failure."""
    return ActionResult(
        data={
            "success": False,
            "partial_success": True,
            "message": str(message),
            **kwargs,
        },
        cost_usd=0,
    )


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
    if not isinstance(response_data, dict):
        raise Exception("Shopify returned an invalid GraphQL response")
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
        filters.append(f"created_at:>{escape_graphql_query_value(inputs['created_at_min'])}")
    if inputs.get("created_at_max"):
        filters.append(f"created_at:<{escape_graphql_query_value(inputs['created_at_max'])}")

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
    variants_connection = graphql_product.get("variants", {})
    variants_data = variants_connection
    if isinstance(variants_data, dict):
        variants_data = variants_data.get("nodes", []) or variants_data.get("edges", [])
    if variants_data and isinstance(variants_data[0], dict) and "node" in variants_data[0]:
        variants_data = [e["node"] for e in variants_data]

    product["variants"] = [transform_variant_response(variant) for variant in (variants_data or [])]
    add_connection_metadata(product, "variants", variants_connection)

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
    images_connection = graphql_product.get("images", {})
    images_data = images_connection
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
    add_connection_metadata(product, "images", images_connection)

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


def raise_for_user_errors(operation: str, payload: dict, key: str = "userErrors") -> None:
    """Raise one consistent exception for mutation-level Shopify errors."""
    user_errors = payload.get(key) or []
    if user_errors:
        raise Exception(format_graphql_user_errors(operation, user_errors))


def connection_nodes(connection: dict) -> list:
    """Return nodes from either GraphQL connection representation."""
    if isinstance(connection, list):
        return connection
    if not isinstance(connection, dict):
        return []
    nodes = connection.get("nodes")
    if isinstance(nodes, list):
        return nodes
    return [edge.get("node", {}) for edge in connection.get("edges", []) if isinstance(edge, dict)]


def add_connection_metadata(result: dict, field_name: str, connection: dict) -> dict:
    """Add explicit pagination metadata for a nested GraphQL connection."""
    page_info = connection.get("pageInfo") if isinstance(connection, dict) else {}
    if not isinstance(page_info, dict):
        page_info = {}
    result[f"{field_name}_has_next_page"] = bool(page_info.get("hasNextPage", False))
    if page_info.get("endCursor") is not None:
        result[f"{field_name}_end_cursor"] = page_info["endCursor"]
    return result


def comma_list(value: Any) -> list:
    """Normalize comma-delimited or list inputs to a clean string list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def clamp_limit(value: Any, default: int = 50, maximum: int = 250) -> int:
    """Normalize Shopify connection page sizes."""
    return max(1, min(int(value or default), maximum))


def graphql_address(address: dict) -> dict:
    """Convert REST-style address keys to MailingAddressInput keys."""
    if not isinstance(address, dict):
        return {}
    mapping = {
        "first_name": "firstName",
        "last_name": "lastName",
        "country_code": "countryCode",
        "province_code": "provinceCode",
    }
    allowed = {
        "address1",
        "address2",
        "city",
        "company",
        "country",
        "countryCode",
        "firstName",
        "lastName",
        "phone",
        "province",
        "provinceCode",
        "zip",
    }
    normalized = {mapping.get(key, key): value for key, value in address.items() if value is not None}
    return {key: value for key, value in normalized.items() if key in allowed}


def transform_address(address: dict) -> dict:
    """Convert a GraphQL address to the established REST-style response."""
    if not address:
        return {}
    return {
        "id": from_gid(address.get("id", "")),
        "first_name": address.get("firstName"),
        "last_name": address.get("lastName"),
        "company": address.get("company"),
        "address1": address.get("address1"),
        "address2": address.get("address2"),
        "city": address.get("city"),
        "province": address.get("province"),
        "province_code": address.get("provinceCode"),
        "country": address.get("country"),
        "country_code": address.get("countryCodeV2"),
        "zip": address.get("zip"),
        "phone": address.get("phone"),
    }


def transform_customer_response(customer: dict) -> dict:
    """Convert a GraphQL customer to the established response shape."""
    if not customer:
        return {}
    addresses_connection = customer.get("addressesV2", {})
    addresses = [transform_address(address) for address in connection_nodes(addresses_connection)]
    default_email = customer.get("defaultEmailAddress") or {}
    default_phone = customer.get("defaultPhoneNumber") or {}
    result = {
        "id": from_gid(customer.get("id", "")),
        "email": default_email.get("emailAddress"),
        "first_name": customer.get("firstName"),
        "last_name": customer.get("lastName"),
        "phone": default_phone.get("phoneNumber"),
        "verified_email": customer.get("verifiedEmail"),
        "note": customer.get("note"),
        "tags": ", ".join(customer.get("tags") or []),
        "tax_exempt": customer.get("taxExempt"),
        "created_at": customer.get("createdAt"),
        "updated_at": customer.get("updatedAt"),
        "default_address": transform_address(customer.get("defaultAddress") or {}),
        "addresses": addresses,
    }
    return add_connection_metadata(result, "addresses", addresses_connection)


def money_amount(money_set: dict) -> str | None:
    """Extract the shop-currency amount from a MoneyBag."""
    return ((money_set or {}).get("shopMoney") or {}).get("amount")


def transform_order_response(order: dict) -> dict:
    """Convert a GraphQL order to a REST-compatible response."""
    if not order:
        return {}
    line_items_connection = order.get("lineItems", {})
    line_items = []
    for item in connection_nodes(line_items_connection):
        variant = item.get("variant") or {}
        line_items.append(
            {
                "id": from_gid(item.get("id", "")),
                "variant_id": from_gid(variant.get("id", "")),
                "title": item.get("title"),
                "quantity": item.get("quantity"),
                "sku": item.get("sku"),
                "price": money_amount(item.get("originalUnitPriceSet")),
            }
        )
    result = {
        "id": from_gid(order.get("id", "")),
        "name": order.get("name"),
        "email": order.get("email"),
        "created_at": order.get("createdAt"),
        "updated_at": order.get("updatedAt"),
        "cancelled_at": order.get("cancelledAt"),
        "financial_status": (order.get("displayFinancialStatus") or "").lower(),
        "fulfillment_status": (order.get("displayFulfillmentStatus") or "").lower(),
        "note": order.get("note"),
        "tags": ", ".join(order.get("tags") or []),
        "total_price": money_amount(order.get("totalPriceSet")),
        "currency": ((order.get("totalPriceSet") or {}).get("shopMoney") or {}).get("currencyCode"),
        "shipping_address": transform_address(order.get("shippingAddress") or {}),
        "billing_address": transform_address(order.get("billingAddress") or {}),
        "line_items": line_items,
    }
    return add_connection_metadata(result, "line_items", line_items_connection)


def transform_location_response(location: dict) -> dict:
    """Convert a GraphQL location to a REST-compatible response."""
    if not location:
        return {}
    address = location.get("address") or {}
    return {
        "id": from_gid(location.get("id", "")),
        "name": location.get("name"),
        "active": location.get("isActive"),
        "fulfills_online_orders": location.get("fulfillsOnlineOrders"),
        "address1": address.get("address1"),
        "address2": address.get("address2"),
        "city": address.get("city"),
        "province": address.get("province"),
        "province_code": address.get("provinceCode"),
        "country": address.get("country"),
        "country_code": address.get("countryCode"),
        "zip": address.get("zip"),
        "phone": address.get("phone"),
    }


def transform_inventory_level_response(level: dict) -> dict:
    """Convert a GraphQL inventory level to a REST-compatible response."""
    quantities = {entry.get("name"): entry.get("quantity") for entry in level.get("quantities", [])}
    return {
        "id": from_gid(level.get("id", "")),
        "inventory_item_id": from_gid((level.get("item") or {}).get("id", "")),
        "location_id": from_gid((level.get("location") or {}).get("id", "")),
        "available": quantities.get("available"),
        "updated_at": level.get("updatedAt"),
    }


def build_fulfillment_order_payload(fulfillment_orders: list, location_id: str, requested_line_items: list) -> list:
    """Map order line items to Shopify's fulfillment-order based request shape."""
    eligible_orders = []
    for fulfillment_order in fulfillment_orders:
        supported_actions = [str(action).lower() for action in fulfillment_order.get("supported_actions", [])]
        if str(fulfillment_order.get("assigned_location_id")) != str(location_id):
            continue
        if supported_actions and "create_fulfillment" not in supported_actions:
            continue
        eligible_orders.append(fulfillment_order)

    if not eligible_orders:
        raise ValueError(f"No fulfillable fulfillment orders were found at location {location_id}")

    if not requested_line_items:
        return [
            {"fulfillmentOrderId": to_gid("FulfillmentOrder", fulfillment_order["id"])}
            for fulfillment_order in eligible_orders
        ]

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
                    "id": to_gid("FulfillmentOrderLineItem", fulfillment_order_line_item["id"]),
                    "quantity": quantity,
                }
            )
            matched_ids.add(requested_id)

        if fulfillment_order_line_items:
            line_items_by_fulfillment_order.append(
                {
                    "fulfillmentOrderId": to_gid("FulfillmentOrder", fulfillment_order["id"]),
                    "fulfillmentOrderLineItems": fulfillment_order_line_items,
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
          pageInfo { hasNextPage endCursor }
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
          pageInfo { hasNextPage endCursor }
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
      pageInfo { hasNextPage endCursor }
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
      pageInfo { hasNextPage endCursor }
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
        pageInfo { hasNextPage endCursor }
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
        pageInfo { hasNextPage endCursor }
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
        pageInfo { hasNextPage endCursor }
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
        pageInfo { hasNextPage endCursor }
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

CUSTOMER_FIELDS = """
  id firstName lastName note tags taxExempt createdAt updatedAt verifiedEmail
  defaultEmailAddress { emailAddress }
  defaultPhoneNumber { phoneNumber }
  defaultAddress {
    id firstName lastName company address1 address2 city province provinceCode
    country countryCodeV2 zip phone
  }
  addressesV2(first: 10) {
    nodes {
      id firstName lastName company address1 address2 city province provinceCode
      country countryCodeV2 zip phone
    }
    pageInfo { hasNextPage endCursor }
  }
"""
CUSTOMERS_QUERY = f"""
query Customers($first: Int!, $after: String, $query: String) {{
  customers(first: $first, after: $after, query: $query, sortKey: ID) {{
    nodes {{ {CUSTOMER_FIELDS} }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
CUSTOMER_QUERY = f"query Customer($id: ID!) {{ customer(id: $id) {{ {CUSTOMER_FIELDS} }} }}"
CUSTOMER_CREATE_MUTATION = f"""
mutation CustomerCreate($input: CustomerInput!) {{
  customerCreate(input: $input) {{ customer {{ {CUSTOMER_FIELDS} }} userErrors {{ field message }} }}
}}
"""
CUSTOMER_UPDATE_MUTATION = f"""
mutation CustomerUpdate($input: CustomerInput!) {{
  customerUpdate(input: $input) {{ customer {{ {CUSTOMER_FIELDS} }} userErrors {{ field message }} }}
}}
"""
CUSTOMER_INVITE_MUTATION = """
mutation CustomerInvite($customerId: ID!) {
  customerSendAccountInviteEmail(customerId: $customerId) {
    customer { id }
    userErrors { field message }
  }
}
"""

ORDER_FIELDS = """
  id name email createdAt updatedAt cancelledAt displayFinancialStatus displayFulfillmentStatus note tags
  totalPriceSet { shopMoney { amount currencyCode } }
  shippingAddress {
    id firstName lastName company address1 address2 city province provinceCode
    country countryCodeV2 zip phone
  }
  billingAddress {
    id firstName lastName company address1 address2 city province provinceCode
    country countryCodeV2 zip phone
  }
  lineItems(first: 100) {
    nodes { id title quantity sku originalUnitPriceSet { shopMoney { amount currencyCode } } variant { id } }
    pageInfo { hasNextPage endCursor }
  }
"""
ORDERS_QUERY = f"""
query Orders($first: Int!, $after: String, $query: String) {{
  orders(first: $first, after: $after, query: $query, sortKey: ID) {{
    nodes {{ {ORDER_FIELDS} }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
ORDER_QUERY = f"query Order($id: ID!) {{ order(id: $id) {{ {ORDER_FIELDS} }} }}"
ORDER_CREATE_MUTATION = f"""
mutation OrderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {{
  orderCreate(order: $order, options: $options) {{ order {{ {ORDER_FIELDS} }} userErrors {{ field message }} }}
}}
"""
ORDER_CANCEL_MUTATION = """
mutation OrderCancel(
  $orderId: ID!, $notifyCustomer: Boolean, $refundMethod: OrderCancelRefundMethodInput!,
  $restock: Boolean!, $reason: OrderCancelReason!
) {
  orderCancel(
    orderId: $orderId, notifyCustomer: $notifyCustomer, refundMethod: $refundMethod,
    restock: $restock, reason: $reason
  ) {
    job { id done }
    orderCancelUserErrors { field message code }
  }
}
"""

INVENTORY_ITEMS_QUERY = """
query InventoryItems($ids: [ID!]!, $first: Int!) {
  nodes(ids: $ids) {
    ... on InventoryItem {
      id
      inventoryLevels(first: $first) {
        nodes { id updatedAt item { id } location { id } quantities(names: ["available"]) { name quantity } }
      }
    }
  }
}
"""
LOCATION_INVENTORY_QUERY = """
query LocationInventory($ids: [ID!]!, $first: Int!) {
  nodes(ids: $ids) {
    ... on Location {
      id
      inventoryLevels(first: $first) {
        nodes { id updatedAt item { id } location { id } quantities(names: ["available"]) { name quantity } }
      }
    }
  }
}
"""
INVENTORY_SET_MUTATION = """
mutation InventorySet($input: InventorySetQuantitiesInput!, $idempotencyKey: String!) {
  inventorySetQuantities(input: $input) @idempotent(key: $idempotencyKey) {
    inventoryAdjustmentGroup { changes { name quantityAfterChange } }
    userErrors { field message code }
  }
}
"""

LOCATION_FIELDS = """
  id name isActive fulfillsOnlineOrders
  address { address1 address2 city province provinceCode country countryCode zip phone }
"""
LOCATIONS_QUERY = f"""
query Locations($after: String) {{
  locations(first: 250, after: $after) {{
    nodes {{ {LOCATION_FIELDS} }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
LOCATION_QUERY = f"query Location($id: ID!) {{ location(id: $id) {{ {LOCATION_FIELDS} }} }}"
SHOP_QUERY = """
query Shop {
  shop {
    id name email myshopifyDomain currencyCode ianaTimezone
    primaryDomain { host url }
    shopAddress { address1 address2 city province provinceCode country countryCodeV2 zip phone }
  }
}
"""
SHOP_CURRENCY_QUERY = "query ShopCurrency { shop { currencyCode } }"

DRAFT_ORDER_FIELDS = """
  id name email status invoiceUrl note2 tags createdAt updatedAt completedAt
  customer { id }
  order { id }
  shippingAddress {
    id firstName lastName company address1 address2 city province provinceCode
    country countryCodeV2 zip phone
  }
  billingAddress {
    id firstName lastName company address1 address2 city province provinceCode
    country countryCodeV2 zip phone
  }
  lineItems(first: 100) {
    nodes { id title quantity sku originalUnitPriceSet { shopMoney { amount currencyCode } } variant { id } }
    pageInfo { hasNextPage endCursor }
  }
"""
DRAFT_ORDERS_QUERY = f"""
query DraftOrders($first: Int!, $after: String, $query: String) {{
  draftOrders(first: $first, after: $after, query: $query, sortKey: ID) {{
    nodes {{ {DRAFT_ORDER_FIELDS} }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
DRAFT_CREATE_MUTATION = f"""
mutation DraftCreate($input: DraftOrderInput!) {{
  draftOrderCreate(input: $input) {{ draftOrder {{ {DRAFT_ORDER_FIELDS} }} userErrors {{ field message }} }}
}}
"""
DRAFT_COMPLETE_MUTATION = f"""
mutation DraftComplete($id: ID!, $paymentPending: Boolean) {{
  draftOrderComplete(id: $id, paymentPending: $paymentPending) {{
    draftOrder {{ {DRAFT_ORDER_FIELDS} }} userErrors {{ field message }}
  }}
}}
"""
DRAFT_DELETE_MUTATION = """
mutation DraftDelete($input: DraftOrderDeleteInput!) {
  draftOrderDelete(input: $input) { deletedId userErrors { field message } }
}
"""

FULFILLMENT_FIELDS = """
  id status createdAt updatedAt
  trackingInfo { company number url }
"""
ORDER_FULFILLMENTS_QUERY = f"""
query OrderFulfillments($id: ID!) {{
  order(id: $id) {{ fulfillments(first: 250) {{ {FULFILLMENT_FIELDS} }} }}
}}
"""
FULFILLMENT_ORDERS_QUERY = """
query FulfillmentOrders($id: ID!) {
  order(id: $id) {
    fulfillmentOrders(first: 250) {
      nodes {
        id supportedActions { action }
        assignedLocation { location { id } }
        lineItems(first: 250) { nodes { id totalQuantity remainingQuantity lineItem { id } } }
      }
    }
  }
}
"""
FULFILLMENT_CREATE_MUTATION = f"""
mutation FulfillmentCreate($fulfillment: FulfillmentInput!) {{
  fulfillmentCreate(fulfillment: $fulfillment) {{
    fulfillment {{ {FULFILLMENT_FIELDS} }}
    userErrors {{ field message }}
  }}
}}
"""
FULFILLMENT_TRACKING_MUTATION = f"""
mutation FulfillmentTracking($id: ID!, $input: FulfillmentTrackingInput!, $notify: Boolean) {{
  fulfillmentTrackingInfoUpdate(fulfillmentId: $id, trackingInfoInput: $input, notifyCustomer: $notify) {{
    fulfillment {{ {FULFILLMENT_FIELDS} }} userErrors {{ field message }}
  }}
}}
"""


def transform_draft_order_response(draft: dict) -> dict:
    """Convert a GraphQL draft order to a REST-compatible response."""
    if not draft:
        return {}
    line_items_connection = draft.get("lineItems", {})
    line_items = []
    for item in connection_nodes(line_items_connection):
        line_items.append(
            {
                "id": from_gid(item.get("id", "")),
                "variant_id": from_gid((item.get("variant") or {}).get("id", "")),
                "title": item.get("title"),
                "quantity": item.get("quantity"),
                "sku": item.get("sku"),
                "price": money_amount(item.get("originalUnitPriceSet")),
            }
        )
    result = {
        "id": from_gid(draft.get("id", "")),
        "name": draft.get("name"),
        "email": draft.get("email"),
        "status": (draft.get("status") or "").lower(),
        "invoice_url": draft.get("invoiceUrl"),
        "note": draft.get("note2"),
        "tags": ", ".join(draft.get("tags") or []),
        "created_at": draft.get("createdAt"),
        "updated_at": draft.get("updatedAt"),
        "completed_at": draft.get("completedAt"),
        "customer": {"id": from_gid((draft.get("customer") or {}).get("id", ""))},
        "order_id": from_gid((draft.get("order") or {}).get("id", "")),
        "shipping_address": transform_address(draft.get("shippingAddress") or {}),
        "billing_address": transform_address(draft.get("billingAddress") or {}),
        "line_items": line_items,
    }
    return add_connection_metadata(result, "line_items", line_items_connection)


def transform_fulfillment_response(fulfillment: dict) -> dict:
    """Convert a GraphQL fulfillment to a REST-compatible response."""
    if not fulfillment:
        return {}
    tracking = (fulfillment.get("trackingInfo") or [{}])[0] or {}
    return {
        "id": from_gid(fulfillment.get("id", "")),
        "status": (fulfillment.get("status") or "").lower(),
        "created_at": fulfillment.get("createdAt"),
        "updated_at": fulfillment.get("updatedAt"),
        "tracking_company": tracking.get("company"),
        "tracking_number": tracking.get("number"),
        "tracking_url": tracking.get("url"),
    }


def graphql_order_line_items(line_items: list, currency_code: str | None = None) -> list:
    """Convert existing REST-style line items to OrderCreateLineItemInput."""
    result = []
    for item in line_items:
        if not isinstance(item, dict):
            raise ValueError("Each line_items entry must be an object")
        converted = {"quantity": int(item.get("quantity", 1))}
        if item.get("variant_id") or item.get("variantId"):
            converted["variantId"] = to_gid("ProductVariant", item.get("variant_id") or item["variantId"])
        for field in ("title", "sku", "taxable", "requiresShipping"):
            source = "requires_shipping" if field == "requiresShipping" else field
            if item.get(source) is not None:
                converted[field] = item[source]
        if item.get("price") is not None:
            if not currency_code:
                raise ValueError("Shop currency is required for custom order line-item prices")
            converted["priceSet"] = {"shopMoney": {"amount": item["price"], "currencyCode": currency_code}}
        result.append(converted)
    return result


def graphql_draft_line_items(line_items: list, currency_code: str | None = None) -> list:
    """Convert existing REST-style line items to DraftOrderLineItemInput."""
    result = []
    for item in line_items:
        if not isinstance(item, dict):
            raise ValueError("Each line_items entry must be an object")
        converted = {"quantity": int(item.get("quantity", 1))}
        if item.get("variant_id") or item.get("variantId"):
            converted["variantId"] = to_gid("ProductVariant", item.get("variant_id") or item["variantId"])
        if item.get("title") is not None:
            converted["title"] = item["title"]
        if item.get("price") is not None:
            if not currency_code:
                raise ValueError("Shop currency is required for custom draft-order line-item prices")
            converted["originalUnitPriceWithCurrency"] = {
                "amount": item["price"],
                "currencyCode": currency_code,
            }
        result.append(converted)
    return result


# ============================================================================
# Customer Actions
# ============================================================================


@shopify_admin.action("list_customers")
class ListCustomersHandler(ActionHandler):
    """List customers with optional filtering and pagination."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filters = []
            filter_values = (
                (inputs.get("since_id"), "id", ">"),
                (inputs.get("created_at_min"), "customer_date", ">="),
                (inputs.get("created_at_max"), "customer_date", "<="),
                (inputs.get("updated_at_min"), "updated_at", ">="),
                (inputs.get("updated_at_max"), "updated_at", "<="),
            )
            for value, field, operator in filter_values:
                if value:
                    filters.append(f"{field}:{operator}{escape_graphql_query_value(value)}")
            variables = {"first": clamp_limit(inputs.get("limit")), "query": " AND ".join(filters) or None}
            if inputs.get("after") is not None:
                variables["after"] = inputs["after"]
            data = await execute_graphql(
                context,
                CUSTOMERS_QUERY,
                variables,
            )
            customers_connection = data.get("customers", {})
            customers = [transform_customer_response(item) for item in connection_nodes(customers_connection)]
            page_info = customers_connection.get("pageInfo", {})
            result_data = {
                "customers": customers,
                "count": len(customers),
                "hasNextPage": page_info.get("hasNextPage", False),
            }
            if page_info.get("endCursor") is not None:
                result_data["endCursor"] = page_info["endCursor"]
            return success_response(**result_data)
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("get_customer")
class GetCustomerHandler(ActionHandler):
    """Get a single customer by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await execute_graphql(context, CUSTOMER_QUERY, {"id": to_gid("Customer", inputs["customer_id"])})
            customer = data.get("customer")
            if not customer:
                raise ValueError(f"Customer {inputs['customer_id']} was not found")
            return success_response(customer=transform_customer_response(customer))
        except Exception as e:
            return error_response(e, customer={})


@shopify_admin.action("search_customers")
class SearchCustomersHandler(ActionHandler):
    """Search customers by query string."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {"first": clamp_limit(inputs.get("limit")), "query": inputs["query"]}
            if inputs.get("after") is not None:
                variables["after"] = inputs["after"]
            data = await execute_graphql(
                context,
                CUSTOMERS_QUERY,
                variables,
            )
            customers_connection = data.get("customers", {})
            customers = [transform_customer_response(item) for item in connection_nodes(customers_connection)]
            page_info = customers_connection.get("pageInfo", {})
            result_data = {
                "customers": customers,
                "count": len(customers),
                "hasNextPage": page_info.get("hasNextPage", False),
            }
            if page_info.get("endCursor") is not None:
                result_data["endCursor"] = page_info["endCursor"]
            return success_response(**result_data)
        except Exception as e:
            return error_response(e, customers=[], count=0)


@shopify_admin.action("create_customer")
class CreateCustomerHandler(ActionHandler):
    """Create a new customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            if inputs.get("verified_email") is False:
                raise ValueError(
                    "verified_email=false is not supported by Shopify GraphQL; email verification is managed by Shopify"
                )
            customer_fields = {
                "email": inputs.get("email"),
                "firstName": inputs.get("first_name"),
                "lastName": inputs.get("last_name"),
                "phone": inputs.get("phone"),
                "tags": inputs.get("tags"),
                "note": inputs.get("note"),
                "taxExempt": inputs.get("tax_exempt"),
            }
            customer_input = {field: value for field, value in customer_fields.items() if value is not None}
            if customer_input.get("tags") is not None:
                customer_input["tags"] = comma_list(customer_input["tags"])
            if inputs.get("address"):
                customer_input["addresses"] = [graphql_address(inputs["address"])]
            data = await execute_graphql(context, CUSTOMER_CREATE_MUTATION, {"input": customer_input})
            payload = data.get("customerCreate", {})
            raise_for_user_errors("Customer creation", payload)
            customer = payload.get("customer") or {}
            transformed_customer = transform_customer_response(customer)
            if inputs.get("send_email_welcome") and customer.get("id"):
                try:
                    invite_data = await execute_graphql(
                        context,
                        CUSTOMER_INVITE_MUTATION,
                        {"customerId": customer["id"]},
                    )
                    raise_for_user_errors(
                        "Customer account invitation",
                        invite_data.get("customerSendAccountInviteEmail", {}),
                    )
                except Exception as e:
                    return partial_success_response(
                        f"Customer was created, but the welcome email could not be sent: {e}",
                        customer=transformed_customer,
                    )
            return success_response(customer=transformed_customer)
        except Exception as e:
            return error_response(e, customer={})


@shopify_admin.action("update_customer")
class UpdateCustomerHandler(ActionHandler):
    """Update an existing customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_input = {"id": to_gid("Customer", inputs["customer_id"])}
            customer_fields = {
                "email": inputs.get("email"),
                "firstName": inputs.get("first_name"),
                "lastName": inputs.get("last_name"),
                "phone": inputs.get("phone"),
                "tags": inputs.get("tags"),
                "note": inputs.get("note"),
                "taxExempt": inputs.get("tax_exempt"),
            }
            customer_input.update({field: value for field, value in customer_fields.items() if value is not None})
            if customer_input.get("tags") is not None:
                customer_input["tags"] = comma_list(customer_input["tags"])
            data = await execute_graphql(context, CUSTOMER_UPDATE_MUTATION, {"input": customer_input})
            payload = data.get("customerUpdate", {})
            raise_for_user_errors("Customer update", payload)
            return success_response(customer=transform_customer_response(payload.get("customer") or {}))
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
            filters = []
            if inputs.get("status") and inputs["status"] != "any":
                filters.append(f"status:{inputs['status']}")
            if inputs.get("financial_status") and inputs["financial_status"] != "any":
                filters.append(f"financial_status:{inputs['financial_status']}")
            if inputs.get("fulfillment_status") and inputs["fulfillment_status"] != "any":
                filters.append(f"fulfillment_status:{inputs['fulfillment_status']}")
            if inputs.get("since_id"):
                filters.append(f"id:>{escape_graphql_query_value(inputs['since_id'])}")
            if inputs.get("created_at_min"):
                filters.append(f"created_at:>={escape_graphql_query_value(inputs['created_at_min'])}")
            if inputs.get("created_at_max"):
                filters.append(f"created_at:<={escape_graphql_query_value(inputs['created_at_max'])}")
            variables = {"first": clamp_limit(inputs.get("limit")), "query": " AND ".join(filters) or None}
            if inputs.get("after") is not None:
                variables["after"] = inputs["after"]
            data = await execute_graphql(
                context,
                ORDERS_QUERY,
                variables,
            )
            orders_connection = data.get("orders", {})
            orders = [transform_order_response(item) for item in connection_nodes(orders_connection)]
            page_info = orders_connection.get("pageInfo", {})
            result_data = {
                "orders": orders,
                "count": len(orders),
                "hasNextPage": page_info.get("hasNextPage", False),
            }
            if page_info.get("endCursor") is not None:
                result_data["endCursor"] = page_info["endCursor"]
            return success_response(**result_data)
        except Exception as e:
            return error_response(e, orders=[], count=0)


@shopify_admin.action("get_order")
class GetOrderHandler(ActionHandler):
    """Get a single order by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await execute_graphql(context, ORDER_QUERY, {"id": to_gid("Order", inputs["order_id"])})
            order = data.get("order")
            if not order:
                raise ValueError(f"Order {inputs['order_id']} was not found")
            return success_response(order=transform_order_response(order))
        except Exception as e:
            return error_response(e, order={})


@shopify_admin.action("create_order")
class CreateOrderHandler(ActionHandler):
    """Create a new order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            currency_code = None
            if any(isinstance(item, dict) and item.get("price") is not None for item in inputs["line_items"]):
                currency_data = await execute_graphql(context, SHOP_CURRENCY_QUERY)
                currency_code = (currency_data.get("shop") or {}).get("currencyCode")
            order_input = {"lineItems": graphql_order_line_items(inputs["line_items"], currency_code)}
            if inputs.get("customer_id"):
                order_input["customer"] = {"toAssociate": {"id": to_gid("Customer", inputs["customer_id"])}}
            order_fields = {
                "email": inputs.get("email"),
                "financialStatus": inputs.get("financial_status"),
                "fulfillmentStatus": inputs.get("fulfillment_status"),
                "note": inputs.get("note"),
            }
            for target, value in order_fields.items():
                if value is not None:
                    order_input[target] = str(value).upper() if target.endswith("Status") else value
            if inputs.get("tags") is not None:
                order_input["tags"] = comma_list(inputs["tags"])
            shipping_address = inputs.get("shipping_address")
            if shipping_address:
                order_input["shippingAddress"] = graphql_address(shipping_address)
            billing_address = inputs.get("billing_address")
            if billing_address:
                order_input["billingAddress"] = graphql_address(billing_address)
            options = {
                "sendReceipt": inputs.get("send_receipt", False),
                "sendFulfillmentReceipt": inputs.get("send_fulfillment_receipt", False),
            }
            data = await execute_graphql(context, ORDER_CREATE_MUTATION, {"order": order_input, "options": options})
            payload = data.get("orderCreate", {})
            raise_for_user_errors("Order creation", payload)
            return success_response(order=transform_order_response(payload.get("order") or {}))
        except Exception as e:
            return error_response(e, order={})


@shopify_admin.action("cancel_order")
class CancelOrderHandler(ActionHandler):
    """Cancel an existing order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_gid = to_gid("Order", inputs["order_id"])
            data = await execute_graphql(
                context,
                ORDER_CANCEL_MUTATION,
                {
                    "orderId": order_gid,
                    "notifyCustomer": inputs.get("email", True),
                    "refundMethod": {"originalPaymentMethodsRefund": True},
                    "restock": inputs.get("restock", True),
                    "reason": str(inputs.get("reason") or "other").upper(),
                },
            )
            payload = data.get("orderCancel", {})
            raise_for_user_errors("Order cancellation", payload, "orderCancelUserErrors")
            job = payload.get("job") or {}
            job_id = job.get("id")
            if not job_id:
                raise Exception("Order cancellation failed: Shopify did not return a cancellation job")

            job_done = bool(job.get("done", False))
            result = {
                "cancellation_status": "completed" if job_done else "pending",
                "job_id": job_id,
                "job_done": job_done,
            }
            if job_done:
                try:
                    order_data = await execute_graphql(context, ORDER_QUERY, {"id": order_gid})
                    result["order"] = transform_order_response(order_data.get("order") or {})
                except Exception as e:
                    result["message"] = (
                        f"Order cancellation completed, but the updated order could not be retrieved: {e}"
                    )
            return success_response(**result)
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
            limit = clamp_limit(inputs.get("limit"))

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

            graphql_product = data.get("product")
            if not graphql_product:
                raise ValueError(f"Product {product_id} was not found")

            # Transform response
            product = transform_product_response(graphql_product)

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
                try:
                    if len(graphql_variants) == 1 and not has_option_values[0]:
                        standalone_variants = (graphql_product.get("variants") or {}).get("nodes", [])
                        if not standalone_variants:
                            raise Exception("Shopify did not return the product's standalone variant")
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
                        raise Exception(format_graphql_user_errors(variant_operation, variant_errors))

                    product_data = await execute_graphql(context, PRODUCT_QUERY, {"id": product_id})
                    graphql_product = product_data.get("product") or {}
                    if not graphql_product:
                        raise Exception("Shopify did not return the product after variant setup")
                except Exception as e:
                    created_product = transform_product_response(graphql_product)
                    if not created_product.get("id"):
                        created_product["id"] = from_gid(product_id)
                    return partial_success_response(
                        f"Product {from_gid(product_id)} was created, but variant setup could not be completed: {e}",
                        product=created_product,
                    )

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
            title = inputs.get("title")
            if title is not None:
                product_input["title"] = title
            body_html = inputs.get("body_html")
            if body_html is not None:
                product_input["descriptionHtml"] = body_html
            vendor = inputs.get("vendor")
            if vendor is not None:
                product_input["vendor"] = vendor
            product_type = inputs.get("product_type")
            if product_type is not None:
                product_input["productType"] = product_type
            tags = inputs.get("tags")
            if tags is not None:
                # Convert comma-separated string to array if needed
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                product_input["tags"] = tags
            status = inputs.get("status")
            if status is not None:
                # Convert to uppercase for GraphQL enum
                product_input["status"] = status.upper()

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
            item_ids = comma_list(inputs.get("inventory_item_ids"))
            location_ids = comma_list(inputs.get("location_ids"))
            if not item_ids and not location_ids:
                return error_response(
                    "Either inventory_item_ids or location_ids is required",
                    inventory_levels=[],
                    count=0,
                )
            limit = clamp_limit(inputs.get("limit"))
            if item_ids:
                data = await execute_graphql(
                    context,
                    INVENTORY_ITEMS_QUERY,
                    {"ids": [to_gid("InventoryItem", item_id) for item_id in item_ids], "first": limit},
                )
            else:
                data = await execute_graphql(
                    context,
                    LOCATION_INVENTORY_QUERY,
                    {"ids": [to_gid("Location", location_id) for location_id in location_ids], "first": limit},
                )
            requested_locations = set(location_ids)
            levels = []
            for node in data.get("nodes", []):
                for level in connection_nodes((node or {}).get("inventoryLevels", {})):
                    if (
                        requested_locations
                        and from_gid((level.get("location") or {}).get("id", "")) not in requested_locations
                    ):
                        continue
                    levels.append(transform_inventory_level_response(level))
            inventory_levels = levels[:limit]
            return success_response(inventory_levels=inventory_levels, count=len(inventory_levels))
        except Exception as e:
            return error_response(e, inventory_levels=[], count=0)


@shopify_admin.action("set_inventory_level")
class SetInventoryLevelHandler(ActionHandler):
    """Set inventory level for an item at a location."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            inventory_item_id = to_gid("InventoryItem", inputs["inventory_item_id"])
            location_id = to_gid("Location", inputs["location_id"])
            variables = {
                "input": {
                    "name": "available",
                    "reason": "correction",
                    "referenceDocumentUri": f"autohive://shopify-admin/inventory/{uuid4()}",
                    "quantities": [
                        {
                            "inventoryItemId": inventory_item_id,
                            "locationId": location_id,
                            "quantity": inputs["available"],
                            "changeFromQuantity": None,
                        }
                    ],
                },
                "idempotencyKey": str(uuid4()),
            }
            data = await execute_graphql(context, INVENTORY_SET_MUTATION, variables)
            payload = data.get("inventorySetQuantities", {})
            raise_for_user_errors("Inventory update", payload)
            changes = (payload.get("inventoryAdjustmentGroup") or {}).get("changes") or []
            available = next(
                (change.get("quantityAfterChange") for change in changes if change.get("name") == "available"),
                None,
            )
            if available is None:
                available = inputs["available"]
            return success_response(
                inventory_level={
                    "inventory_item_id": from_gid(inventory_item_id),
                    "location_id": from_gid(location_id),
                    "available": available,
                }
            )
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
            locations = []
            after = None
            while True:
                data = await execute_graphql(context, LOCATIONS_QUERY, {"after": after})
                connection = data.get("locations", {})
                locations.extend(transform_location_response(item) for item in connection_nodes(connection))
                page_info = connection.get("pageInfo") or {}
                if not page_info.get("hasNextPage"):
                    break
                after = page_info.get("endCursor")
                if not after:
                    raise Exception("Shopify location pagination did not return an end cursor")
            return success_response(locations=locations, count=len(locations))
        except Exception as e:
            return error_response(e, locations=[], count=0)


@shopify_admin.action("get_location")
class GetLocationHandler(ActionHandler):
    """Get a single location by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await execute_graphql(context, LOCATION_QUERY, {"id": to_gid("Location", inputs["location_id"])})
            location = data.get("location")
            if not location:
                raise ValueError(f"Location {inputs['location_id']} was not found")
            return success_response(location=transform_location_response(location))
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
            data = await execute_graphql(context, SHOP_QUERY)
            shop = data.get("shop") or {}
            billing = shop.get("shopAddress") or {}
            result = {
                "id": from_gid(shop.get("id", "")),
                "name": shop.get("name"),
                "email": shop.get("email"),
                "myshopify_domain": shop.get("myshopifyDomain"),
                "domain": (shop.get("primaryDomain") or {}).get("host"),
                "currency": shop.get("currencyCode"),
                "iana_timezone": shop.get("ianaTimezone"),
                "address1": billing.get("address1"),
                "address2": billing.get("address2"),
                "city": billing.get("city"),
                "province": billing.get("province"),
                "province_code": billing.get("provinceCode"),
                "country": billing.get("country"),
                "country_code": billing.get("countryCodeV2"),
                "zip": billing.get("zip"),
                "phone": billing.get("phone"),
            }
            return success_response(shop=result)
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
            filters = []
            if inputs.get("since_id"):
                filters.append(f"id:>{escape_graphql_query_value(inputs['since_id'])}")
            if inputs.get("status") and inputs["status"] != "any":
                filters.append(f"status:{inputs['status']}")
            variables = {"first": clamp_limit(inputs.get("limit")), "query": " AND ".join(filters) or None}
            if inputs.get("after") is not None:
                variables["after"] = inputs["after"]
            data = await execute_graphql(
                context,
                DRAFT_ORDERS_QUERY,
                variables,
            )
            draft_orders_connection = data.get("draftOrders", {})
            draft_orders = [transform_draft_order_response(item) for item in connection_nodes(draft_orders_connection)]
            page_info = draft_orders_connection.get("pageInfo", {})
            result_data = {
                "draft_orders": draft_orders,
                "count": len(draft_orders),
                "hasNextPage": page_info.get("hasNextPage", False),
            }
            if page_info.get("endCursor") is not None:
                result_data["endCursor"] = page_info["endCursor"]
            return success_response(**result_data)
        except Exception as e:
            return error_response(e, draft_orders=[], count=0)


@shopify_admin.action("create_draft_order")
class CreateDraftOrderHandler(ActionHandler):
    """Create a new draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            currency_code = None
            if any(isinstance(item, dict) and item.get("price") is not None for item in inputs["line_items"]):
                currency_data = await execute_graphql(context, SHOP_CURRENCY_QUERY)
                currency_code = (currency_data.get("shop") or {}).get("currencyCode")
            draft_input = {"lineItems": graphql_draft_line_items(inputs["line_items"], currency_code)}
            email = inputs.get("email")
            if email is not None:
                draft_input["email"] = email
            note = inputs.get("note")
            if note is not None:
                draft_input["note"] = note
            if inputs.get("customer_id"):
                draft_input["purchasingEntity"] = {"customerId": to_gid("Customer", inputs["customer_id"])}
            if inputs.get("tags") is not None:
                draft_input["tags"] = comma_list(inputs["tags"])
            shipping_address = inputs.get("shipping_address")
            if shipping_address:
                draft_input["shippingAddress"] = graphql_address(shipping_address)
            billing_address = inputs.get("billing_address")
            if billing_address:
                draft_input["billingAddress"] = graphql_address(billing_address)
            if inputs.get("use_customer_default_address") is not None:
                draft_input["useCustomerDefaultAddress"] = inputs["use_customer_default_address"]
            data = await execute_graphql(context, DRAFT_CREATE_MUTATION, {"input": draft_input})
            payload = data.get("draftOrderCreate", {})
            raise_for_user_errors("Draft order creation", payload)
            return success_response(draft_order=transform_draft_order_response(payload.get("draftOrder") or {}))
        except Exception as e:
            return error_response(e, draft_order={})


@shopify_admin.action("complete_draft_order")
class CompleteDraftOrderHandler(ActionHandler):
    """Complete a draft order, converting it to a real order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            data = await execute_graphql(
                context,
                DRAFT_COMPLETE_MUTATION,
                {
                    "id": to_gid("DraftOrder", inputs["draft_order_id"]),
                    "paymentPending": inputs.get("payment_pending", False),
                },
            )
            payload = data.get("draftOrderComplete", {})
            raise_for_user_errors("Draft order completion", payload)
            return success_response(draft_order=transform_draft_order_response(payload.get("draftOrder") or {}))
        except Exception as e:
            return error_response(e, draft_order={})


@shopify_admin.action("delete_draft_order")
class DeleteDraftOrderHandler(ActionHandler):
    """Delete a draft order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_order_id = inputs["draft_order_id"]
            data = await execute_graphql(
                context,
                DRAFT_DELETE_MUTATION,
                {"input": {"id": to_gid("DraftOrder", draft_order_id)}},
            )
            payload = data.get("draftOrderDelete", {})
            raise_for_user_errors("Draft order deletion", payload)
            if not payload.get("deletedId"):
                raise Exception("Draft order deletion failed: Shopify did not return a deleted ID")
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
            data = await execute_graphql(
                context,
                ORDER_FULFILLMENTS_QUERY,
                {"id": to_gid("Order", inputs["order_id"])},
            )
            order = data.get("order")
            if not order:
                raise ValueError(f"Order {inputs['order_id']} was not found")
            fulfillments = [
                transform_fulfillment_response(item) for item in connection_nodes(order.get("fulfillments", {}))
            ]
            return success_response(fulfillments=fulfillments, count=len(fulfillments))
        except Exception as e:
            return error_response(e, fulfillments=[], count=0)


@shopify_admin.action("create_fulfillment")
class CreateFulfillmentHandler(ActionHandler):
    """Create a fulfillment for an order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = to_gid("Order", inputs["order_id"])
            fulfillment_order_data = await execute_graphql(context, FULFILLMENT_ORDERS_QUERY, {"id": order_id})
            order = fulfillment_order_data.get("order")
            if not order:
                raise ValueError(f"Order {inputs['order_id']} was not found")
            fulfillment_orders = []
            for fulfillment_order in connection_nodes(order.get("fulfillmentOrders", {})):
                fulfillment_orders.append(
                    {
                        "id": from_gid(fulfillment_order.get("id", "")),
                        "assigned_location_id": from_gid(
                            (((fulfillment_order.get("assignedLocation") or {}).get("location") or {}).get("id", ""))
                        ),
                        "supported_actions": [
                            action.get("action") if isinstance(action, dict) else action
                            for action in fulfillment_order.get("supportedActions") or []
                        ],
                        "line_items": [
                            {
                                "id": from_gid(item.get("id", "")),
                                "line_item_id": from_gid((item.get("lineItem") or {}).get("id", "")),
                                "quantity": item.get("totalQuantity"),
                                "fulfillable_quantity": item.get("remainingQuantity"),
                            }
                            for item in connection_nodes(fulfillment_order.get("lineItems", {}))
                        ],
                    }
                )
            line_items_by_fulfillment_order = build_fulfillment_order_payload(
                fulfillment_orders,
                inputs["location_id"],
                inputs.get("line_items") or [],
            )
            fulfillment_input = {
                "lineItemsByFulfillmentOrder": line_items_by_fulfillment_order,
                "notifyCustomer": inputs.get("notify_customer", True),
            }
            tracking_info = {}
            if inputs.get("tracking_number"):
                tracking_info["number"] = inputs["tracking_number"]
            if inputs.get("tracking_company"):
                tracking_info["company"] = inputs["tracking_company"]
            if inputs.get("tracking_url"):
                tracking_info["url"] = inputs["tracking_url"]
            if tracking_info:
                fulfillment_input["trackingInfo"] = tracking_info
            data = await execute_graphql(context, FULFILLMENT_CREATE_MUTATION, {"fulfillment": fulfillment_input})
            payload = data.get("fulfillmentCreate", {})
            raise_for_user_errors("Fulfillment creation", payload)
            return success_response(fulfillment=transform_fulfillment_response(payload.get("fulfillment") or {}))
        except Exception as e:
            return error_response(e, fulfillment={})


@shopify_admin.action("update_fulfillment_tracking")
class UpdateFulfillmentTrackingHandler(ActionHandler):
    """Update tracking information for a fulfillment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            tracking_data = {}
            if inputs.get("tracking_number") is not None:
                tracking_data["number"] = inputs.get("tracking_number")
            if inputs.get("tracking_company") is not None:
                tracking_data["company"] = inputs.get("tracking_company")
            if inputs.get("tracking_url") is not None:
                tracking_data["url"] = inputs.get("tracking_url")

            data = await execute_graphql(
                context,
                FULFILLMENT_TRACKING_MUTATION,
                {
                    "id": to_gid("Fulfillment", inputs["fulfillment_id"]),
                    "input": tracking_data,
                    "notify": inputs.get("notify_customer", False),
                },
            )
            payload = data.get("fulfillmentTrackingInfoUpdate", {})
            raise_for_user_errors("Fulfillment tracking update", payload)
            return success_response(fulfillment=transform_fulfillment_response(payload.get("fulfillment") or {}))
        except Exception as e:
            return error_response(e, fulfillment={})
