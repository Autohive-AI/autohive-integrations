"""
Shopify Storefront API Integration
==================================

Provides access to Shopify's Storefront API for customer-facing operations.

Supported Operations:
- Products: list, get, search
- Collections: list, get
- Cart: create, get, add items, update, remove items, apply discount
- Customer: create, login, get profile, update, recover password

Authentication:
- Public Access Token: X-Shopify-Storefront-Access-Token
- Private Access Token: Shopify-Storefront-Private-Token

Protocol: GraphQL only
API Version: 2024-10
"""

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List
import os

# Create the integration using the config.json
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
shopify_storefront = Integration.load(_config_path)

# Shopify API version
API_VERSION = "2024-10"


# ============================================================================
# Helper Functions
# ============================================================================

def validate_shop_url(shop_url: str) -> str:
    """Validate and sanitize shop URL to prevent SSRF attacks."""
    if not shop_url:
        raise ValueError("Missing required credential: shop_url")

    shop_url = shop_url.replace('https://', '').replace('http://', '')
    shop_url = shop_url.rstrip('/')

    if '/' in shop_url or '@' in shop_url or ':' in shop_url:
        raise ValueError("Invalid shop_url: contains forbidden characters")

    if not shop_url.endswith('.myshopify.com'):
        raise ValueError("shop_url must be a *.myshopify.com domain")

    return shop_url


def get_shop_url(context: ExecutionContext) -> str:
    """Extract and validate the shop URL from context credentials."""
    credentials = context.auth.get('credentials', {})
    shop_url = credentials.get('shop_url', '')
    return validate_shop_url(shop_url)


def get_storefront_url(context: ExecutionContext) -> str:
    """Build Storefront API GraphQL endpoint URL."""
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/api/{API_VERSION}/graphql.json"


def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for Storefront API requests."""
    credentials = context.auth.get('credentials', {})
    auth_type = context.auth.get('auth_type', 'StorefrontPublic')

    headers = {"Content-Type": "application/json"}

    if auth_type == "StorefrontPrivate":
        private_token = credentials.get('private_token')
        if not private_token:
            raise ValueError("Missing required credential: private_token for StorefrontPrivate auth")
        headers["Shopify-Storefront-Private-Token"] = private_token
        if credentials.get('buyer_ip'):
            headers["Shopify-Storefront-Buyer-IP"] = credentials['buyer_ip']
    else:
        public_token = credentials.get('public_token')
        if not public_token:
            raise ValueError("Missing required credential: public_token")
        headers["X-Shopify-Storefront-Access-Token"] = public_token

    return headers


def require_input(inputs: Dict[str, Any], key: str) -> Any:
    """Validate that a required input is present and non-empty."""
    value = inputs.get(key)
    if value is None or value == '':
        raise ValueError(f"Missing required parameter: {key}")
    return value


def require_one_of(inputs: Dict[str, Any], *keys: str) -> None:
    """Validate that at least one of the specified inputs is present."""
    for key in keys:
        if inputs.get(key):
            return
    raise ValueError(f"At least one of these parameters is required: {', '.join(keys)}")


def parse_graphql_response(response: Dict[str, Any]) -> tuple:
    """Parse GraphQL response and extract errors."""
    errors = []

    if not isinstance(response, dict):
        return None, ["Invalid response type from API"]

    for err in response.get('errors', []) or []:
        msg = err.get('message', 'GraphQL error')
        code = (err.get('extensions') or {}).get('code')
        errors.append(f"{code}: {msg}" if code else msg)

    return response.get('data'), errors


def extract_user_errors(data: Dict[str, Any], mutation_key: str, error_key: str = 'userErrors') -> List[str]:
    """Extract user errors from mutation response."""
    if not data:
        return []
    mutation_data = data.get(mutation_key, {}) or {}
    user_errors = mutation_data.get(error_key, []) or []
    return [err.get('message', 'Unknown error') for err in user_errors if err.get('message')]


async def execute_graphql(context: ExecutionContext, query: str,
                          variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute a GraphQL query against the Storefront API."""
    url = get_storefront_url(context)
    headers = build_headers(context)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = await context.fetch(url, method="POST", json=payload, headers=headers)
    return response


def success_response(**kwargs) -> ActionResult:
    """Build standardized success response."""
    return ActionResult(data={"success": True, **kwargs}, cost_usd=0)


def error_response(message: str, **kwargs) -> ActionResult:
    """Build standardized error response."""
    if isinstance(message, list):
        message = "; ".join(message) if message else "Unknown error"
    data = {"success": False, "message": str(message)}
    data.update(kwargs)
    return ActionResult(data=data, cost_usd=0)


def extract_edges(data: Dict, path: str) -> List[Dict]:
    """Extract nodes from GraphQL edges structure."""
    parts = path.split('.')
    current = data
    for part in parts:
        if current is None:
            return []
        current = current.get(part)
    if current and 'edges' in current:
        return [edge['node'] for edge in current['edges']]
    return []


# ============================================================================
# GraphQL Queries
# ============================================================================

QUERY_LIST_PRODUCTS = """
query ListProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    edges {
      cursor
      node {
        id
        title
        handle
        description
        availableForSale
        productType
        vendor
        tags
        priceRange {
          minVariantPrice { amount currencyCode }
          maxVariantPrice { amount currencyCode }
        }
        images(first: 1) {
          edges {
            node { url altText }
          }
        }
        variants(first: 1) {
          edges {
            node { id price { amount currencyCode } }
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

QUERY_GET_PRODUCT = """
query GetProduct($handle: String, $id: ID) {
  product(handle: $handle, id: $id) {
    id
    title
    handle
    description
    descriptionHtml
    availableForSale
    productType
    vendor
    tags
    priceRange {
      minVariantPrice { amount currencyCode }
      maxVariantPrice { amount currencyCode }
    }
    images(first: 10) {
      edges {
        node { id url altText width height }
      }
    }
    variants(first: 100) {
      edges {
        node {
          id
          title
          availableForSale
          quantityAvailable
          price { amount currencyCode }
          compareAtPrice { amount currencyCode }
          selectedOptions { name value }
        }
      }
    }
    options { id name values }
  }
}
"""

QUERY_SEARCH_PRODUCTS = """
query SearchProducts($query: String!, $first: Int!) {
  search(query: $query, first: $first, types: [PRODUCT]) {
    edges {
      node {
        ... on Product {
          id
          title
          handle
          description
          availableForSale
          priceRange {
            minVariantPrice { amount currencyCode }
          }
          images(first: 1) {
            edges { node { url altText } }
          }
        }
      }
    }
    totalCount
  }
}
"""

QUERY_LIST_COLLECTIONS = """
query ListCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        description
        image { url altText }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

QUERY_GET_COLLECTION = """
query GetCollection($handle: String, $id: ID, $first: Int!) {
  collection(handle: $handle, id: $id) {
    id
    title
    handle
    description
    image { url altText }
    products(first: $first) {
      edges {
        node {
          id
          title
          handle
          availableForSale
          priceRange {
            minVariantPrice { amount currencyCode }
          }
          images(first: 1) {
            edges { node { url altText } }
          }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

MUTATION_CREATE_CART = """
mutation CartCreate($input: CartInput!) {
  cartCreate(input: $input) {
    cart {
      id
      checkoutUrl
      totalQuantity
      lines(first: 100) {
        edges {
          node {
            id
            quantity
            merchandise {
              ... on ProductVariant {
                id
                title
                product { title handle }
                price { amount currencyCode }
              }
            }
            cost { totalAmount { amount currencyCode } }
          }
        }
      }
      cost {
        totalAmount { amount currencyCode }
        subtotalAmount { amount currencyCode }
        totalTaxAmount { amount currencyCode }
      }
    }
    userErrors { field message code }
  }
}
"""

QUERY_GET_CART = """
query GetCart($cartId: ID!) {
  cart(id: $cartId) {
    id
    checkoutUrl
    totalQuantity
    lines(first: 100) {
      edges {
        node {
          id
          quantity
          merchandise {
            ... on ProductVariant {
              id
              title
              product { title handle }
              price { amount currencyCode }
            }
          }
          cost { totalAmount { amount currencyCode } }
        }
      }
    }
    cost {
      totalAmount { amount currencyCode }
      subtotalAmount { amount currencyCode }
      totalTaxAmount { amount currencyCode }
    }
    discountCodes { code applicable }
  }
}
"""

MUTATION_ADD_TO_CART = """
mutation CartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {
  cartLinesAdd(cartId: $cartId, lines: $lines) {
    cart {
      id
      totalQuantity
      lines(first: 100) {
        edges {
          node {
            id
            quantity
            merchandise {
              ... on ProductVariant { id title }
            }
          }
        }
      }
      cost { totalAmount { amount currencyCode } }
    }
    userErrors { field message code }
  }
}
"""

MUTATION_UPDATE_CART = """
mutation CartLinesUpdate($cartId: ID!, $lines: [CartLineUpdateInput!]!) {
  cartLinesUpdate(cartId: $cartId, lines: $lines) {
    cart {
      id
      totalQuantity
      lines(first: 100) {
        edges {
          node { id quantity }
        }
      }
      cost { totalAmount { amount currencyCode } }
    }
    userErrors { field message code }
  }
}
"""

MUTATION_REMOVE_FROM_CART = """
mutation CartLinesRemove($cartId: ID!, $lineIds: [ID!]!) {
  cartLinesRemove(cartId: $cartId, lineIds: $lineIds) {
    cart {
      id
      totalQuantity
      cost { totalAmount { amount currencyCode } }
    }
    userErrors { field message code }
  }
}
"""

MUTATION_APPLY_DISCOUNT = """
mutation CartDiscountCodesUpdate($cartId: ID!, $discountCodes: [String!]!) {
  cartDiscountCodesUpdate(cartId: $cartId, discountCodes: $discountCodes) {
    cart {
      id
      discountCodes { code applicable }
      cost { totalAmount { amount currencyCode } }
    }
    userErrors { field message code }
  }
}
"""

MUTATION_CREATE_CUSTOMER = """
mutation CustomerCreate($input: CustomerCreateInput!) {
  customerCreate(input: $input) {
    customer {
      id
      email
      firstName
      lastName
      phone
      acceptsMarketing
    }
    customerUserErrors { field message code }
  }
}
"""

MUTATION_CUSTOMER_LOGIN = """
mutation CustomerAccessTokenCreate($input: CustomerAccessTokenCreateInput!) {
  customerAccessTokenCreate(input: $input) {
    customerAccessToken {
      accessToken
      expiresAt
    }
    customerUserErrors { field message code }
  }
}
"""

QUERY_GET_CUSTOMER = """
query GetCustomer($customerAccessToken: String!) {
  customer(customerAccessToken: $customerAccessToken) {
    id
    email
    firstName
    lastName
    phone
    acceptsMarketing
    defaultAddress {
      id address1 address2 city province country zip
    }
    addresses(first: 10) {
      edges {
        node { id address1 city province country zip }
      }
    }
    orders(first: 10) {
      edges {
        node {
          id
          orderNumber
          totalPrice { amount currencyCode }
          processedAt
          fulfillmentStatus
        }
      }
    }
  }
}
"""

MUTATION_CUSTOMER_RECOVER = """
mutation CustomerRecover($email: String!) {
  customerRecover(email: $email) {
    customerUserErrors { field message code }
  }
}
"""

MUTATION_CUSTOMER_UPDATE = """
mutation CustomerUpdate($customerAccessToken: String!, $customer: CustomerUpdateInput!) {
  customerUpdate(customerAccessToken: $customerAccessToken, customer: $customer) {
    customer {
      id
      email
      firstName
      lastName
      phone
      acceptsMarketing
    }
    customerAccessToken {
      accessToken
      expiresAt
    }
    customerUserErrors { field message code }
  }
}
"""


# ============================================================================
# Product Actions
# ============================================================================

@shopify_storefront.action("storefront_list_products")
class ListProductsHandler(ActionHandler):
    """List products from the storefront."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {
                "first": inputs.get('first', 20),
                "after": inputs.get('after'),
                "query": inputs.get('query')
            }

            response = await execute_graphql(context, QUERY_LIST_PRODUCTS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], products=[])

            data = response.get('data', {})
            products = extract_edges(data, 'products')
            page_info = data.get('products', {}).get('pageInfo', {})

            return success_response(
                products=products,
                count=len(products),
                has_next_page=page_info.get('hasNextPage', False),
                end_cursor=page_info.get('endCursor')
            )
        except Exception as e:
            return error_response(e, products=[], count=0)


@shopify_storefront.action("storefront_get_product")
class GetProductHandler(ActionHandler):
    """Get a single product by handle or ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            require_one_of(inputs, 'handle', 'product_id')

            variables = {
                "handle": inputs.get('handle'),
                "id": inputs.get('product_id')
            }

            response = await execute_graphql(context, QUERY_GET_PRODUCT, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, product=None)

            product = (data or {}).get('product')
            if not product:
                return error_response("Product not found", product=None)

            return success_response(product=product)
        except Exception as e:
            return error_response(str(e), product=None)


@shopify_storefront.action("storefront_search_products")
class SearchProductsHandler(ActionHandler):
    """Search products by keyword."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {
                "query": inputs['query'],
                "first": inputs.get('first', 20)
            }

            response = await execute_graphql(context, QUERY_SEARCH_PRODUCTS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], products=[])

            data = response.get('data', {})
            products = extract_edges(data, 'search')
            total_count = data.get('search', {}).get('totalCount', 0)

            return success_response(
                products=products,
                count=len(products),
                total_count=total_count
            )
        except Exception as e:
            return error_response(e, products=[], count=0)


# ============================================================================
# Collection Actions
# ============================================================================

@shopify_storefront.action("storefront_list_collections")
class ListCollectionsHandler(ActionHandler):
    """List collections from the storefront."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {
                "first": inputs.get('first', 20),
                "after": inputs.get('after')
            }

            response = await execute_graphql(context, QUERY_LIST_COLLECTIONS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], collections=[])

            data = response.get('data', {})
            collections = extract_edges(data, 'collections')
            page_info = data.get('collections', {}).get('pageInfo', {})

            return success_response(
                collections=collections,
                count=len(collections),
                has_next_page=page_info.get('hasNextPage', False),
                end_cursor=page_info.get('endCursor')
            )
        except Exception as e:
            return error_response(e, collections=[], count=0)


@shopify_storefront.action("storefront_get_collection")
class GetCollectionHandler(ActionHandler):
    """Get a collection with its products."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            require_one_of(inputs, 'handle', 'collection_id')

            variables = {
                "handle": inputs.get('handle'),
                "id": inputs.get('collection_id'),
                "first": inputs.get('products_first', 20)
            }

            response = await execute_graphql(context, QUERY_GET_COLLECTION, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, collection=None)

            collection = (data or {}).get('collection')
            if not collection:
                return error_response("Collection not found", collection=None)

            return success_response(collection=collection)
        except Exception as e:
            return error_response(str(e), collection=None)


# ============================================================================
# Cart Actions
# ============================================================================

@shopify_storefront.action("storefront_create_cart")
class CreateCartHandler(ActionHandler):
    """Create a new shopping cart."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_input = {}

            if inputs.get('lines'):
                cart_input['lines'] = inputs['lines']

            if inputs.get('buyer_identity'):
                cart_input['buyerIdentity'] = inputs['buyer_identity']

            variables = {"input": cart_input}
            response = await execute_graphql(context, MUTATION_CREATE_CART, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], cart=None)

            data = response.get('data', {}).get('cartCreate', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'], cart=None)

            return success_response(cart=data.get('cart'))
        except Exception as e:
            return error_response(e, cart=None)


@shopify_storefront.action("storefront_get_cart")
class GetCartHandler(ActionHandler):
    """Get cart contents."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_id = require_input(inputs, 'cart_id')
            variables = {"cartId": cart_id}
            response = await execute_graphql(context, QUERY_GET_CART, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, cart=None)

            cart = (data or {}).get('cart')
            if not cart:
                return error_response("Cart not found", cart=None)

            return success_response(cart=cart)
        except Exception as e:
            return error_response(str(e), cart=None)


@shopify_storefront.action("storefront_add_to_cart")
class AddToCartHandler(ActionHandler):
    """Add items to cart."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_id = require_input(inputs, 'cart_id')
            lines = require_input(inputs, 'lines')

            if not isinstance(lines, list) or len(lines) == 0:
                raise ValueError("lines must be a non-empty array")

            variables = {"cartId": cart_id, "lines": lines}
            response = await execute_graphql(context, MUTATION_ADD_TO_CART, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, cart=None)

            user_errors = extract_user_errors(data, 'cartLinesAdd')
            if user_errors:
                return error_response(user_errors, cart=None)

            return success_response(cart=(data or {}).get('cartLinesAdd', {}).get('cart'))
        except Exception as e:
            return error_response(str(e), cart=None)


@shopify_storefront.action("storefront_update_cart_line")
class UpdateCartLineHandler(ActionHandler):
    """Update cart line item quantity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_id = require_input(inputs, 'cart_id')
            lines = require_input(inputs, 'lines')

            if not isinstance(lines, list) or len(lines) == 0:
                raise ValueError("lines must be a non-empty array")

            variables = {"cartId": cart_id, "lines": lines}
            response = await execute_graphql(context, MUTATION_UPDATE_CART, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, cart=None)

            user_errors = extract_user_errors(data, 'cartLinesUpdate')
            if user_errors:
                return error_response(user_errors, cart=None)

            return success_response(cart=(data or {}).get('cartLinesUpdate', {}).get('cart'))
        except Exception as e:
            return error_response(str(e), cart=None)


@shopify_storefront.action("storefront_remove_from_cart")
class RemoveFromCartHandler(ActionHandler):
    """Remove items from cart."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_id = require_input(inputs, 'cart_id')
            line_ids = require_input(inputs, 'line_ids')

            if not isinstance(line_ids, list) or len(line_ids) == 0:
                raise ValueError("line_ids must be a non-empty array")

            variables = {"cartId": cart_id, "lineIds": line_ids}
            response = await execute_graphql(context, MUTATION_REMOVE_FROM_CART, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, cart=None)

            user_errors = extract_user_errors(data, 'cartLinesRemove')
            if user_errors:
                return error_response(user_errors, cart=None)

            return success_response(cart=(data or {}).get('cartLinesRemove', {}).get('cart'))
        except Exception as e:
            return error_response(str(e), cart=None)


@shopify_storefront.action("storefront_apply_discount")
class ApplyDiscountHandler(ActionHandler):
    """Apply discount codes to cart."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            cart_id = require_input(inputs, 'cart_id')
            discount_codes = require_input(inputs, 'discount_codes')

            if not isinstance(discount_codes, list) or len(discount_codes) == 0:
                raise ValueError("discount_codes must be a non-empty array")

            variables = {"cartId": cart_id, "discountCodes": discount_codes}
            response = await execute_graphql(context, MUTATION_APPLY_DISCOUNT, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, cart=None)

            user_errors = extract_user_errors(data, 'cartDiscountCodesUpdate')
            if user_errors:
                return error_response(user_errors, cart=None)

            return success_response(cart=(data or {}).get('cartDiscountCodesUpdate', {}).get('cart'))
        except Exception as e:
            return error_response(str(e), cart=None)


# ============================================================================
# Customer Actions
# ============================================================================

@shopify_storefront.action("storefront_create_customer")
class CreateCustomerHandler(ActionHandler):
    """Create a new customer account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email = require_input(inputs, 'email')
            password = require_input(inputs, 'password')

            customer_input = {"email": email, "password": password}

            optional_fields = ['firstName', 'lastName', 'phone', 'acceptsMarketing']
            for field in optional_fields:
                snake_field = ''.join(['_' + c.lower() if c.isupper() else c for c in field]).lstrip('_')
                if snake_field in inputs:
                    customer_input[field] = inputs[snake_field]
                elif field in inputs:
                    customer_input[field] = inputs[field]

            variables = {"input": customer_input}
            response = await execute_graphql(context, MUTATION_CREATE_CUSTOMER, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, customer=None)

            user_errors = extract_user_errors(data, 'customerCreate', 'customerUserErrors')
            if user_errors:
                return error_response(user_errors, customer=None)

            return success_response(customer=(data or {}).get('customerCreate', {}).get('customer'))
        except Exception as e:
            return error_response(str(e), customer=None)


@shopify_storefront.action("storefront_customer_login")
class CustomerLoginHandler(ActionHandler):
    """Login customer and get access token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email = require_input(inputs, 'email')
            password = require_input(inputs, 'password')

            variables = {"input": {"email": email, "password": password}}
            response = await execute_graphql(context, MUTATION_CUSTOMER_LOGIN, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, customer_access_token=None)

            user_errors = extract_user_errors(data, 'customerAccessTokenCreate', 'customerUserErrors')
            if user_errors:
                return error_response(user_errors, customer_access_token=None)

            token_data = (data or {}).get('customerAccessTokenCreate', {}).get('customerAccessToken')
            return success_response(
                customer_access_token=token_data.get('accessToken') if token_data else None,
                expires_at=token_data.get('expiresAt') if token_data else None
            )
        except Exception as e:
            return error_response(str(e), customer_access_token=None)


@shopify_storefront.action("storefront_get_customer")
class GetCustomerHandler(ActionHandler):
    """Get customer profile using access token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            access_token = require_input(inputs, 'customer_access_token')
            variables = {"customerAccessToken": access_token}
            response = await execute_graphql(context, QUERY_GET_CUSTOMER, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, customer=None)

            customer = (data or {}).get('customer')
            if not customer:
                return error_response("Customer not found or invalid token", customer=None)

            return success_response(customer=customer)
        except Exception as e:
            return error_response(str(e), customer=None)


@shopify_storefront.action("storefront_recover_customer")
class RecoverCustomerHandler(ActionHandler):
    """Send password recovery email."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email = require_input(inputs, 'email')
            variables = {"email": email}
            response = await execute_graphql(context, MUTATION_CUSTOMER_RECOVER, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors)

            user_errors = extract_user_errors(data, 'customerRecover', 'customerUserErrors')
            if user_errors:
                return error_response(user_errors)

            return success_response(message="Recovery email sent if account exists")
        except Exception as e:
            return error_response(str(e))


@shopify_storefront.action("storefront_update_customer")
class UpdateCustomerHandler(ActionHandler):
    """Update customer profile using access token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            access_token = require_input(inputs, 'customer_access_token')

            customer_input = {}
            field_mappings = {
                'first_name': 'firstName',
                'last_name': 'lastName',
                'phone': 'phone',
                'email': 'email',
                'password': 'password',
                'accepts_marketing': 'acceptsMarketing'
            }

            for snake_key, camel_key in field_mappings.items():
                if snake_key in inputs and inputs[snake_key] is not None:
                    customer_input[camel_key] = inputs[snake_key]

            if not customer_input:
                raise ValueError("At least one customer field must be provided for update")

            variables = {
                "customerAccessToken": access_token,
                "customer": customer_input
            }
            response = await execute_graphql(context, MUTATION_CUSTOMER_UPDATE, variables)
            data, errors = parse_graphql_response(response)

            if errors:
                return error_response(errors, customer=None)

            user_errors = extract_user_errors(data, 'customerUpdate', 'customerUserErrors')
            if user_errors:
                return error_response(user_errors, customer=None)

            update_data = (data or {}).get('customerUpdate', {})
            token_data = update_data.get('customerAccessToken')

            return success_response(
                customer=update_data.get('customer'),
                customer_access_token=token_data.get('accessToken') if token_data else None,
                expires_at=token_data.get('expiresAt') if token_data else None
            )
        except Exception as e:
            return error_response(str(e), customer=None)
