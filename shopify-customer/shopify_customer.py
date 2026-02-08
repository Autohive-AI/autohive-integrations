"""
Shopify Customer Account API Integration
========================================

Provides access to Shopify's Customer Account API for customer self-service.

Supported Operations:
- Profile: get, update
- Addresses: list, create, update, delete, set default
- Orders: list, get

Authentication:
- OAuth 2.0 + PKCE flow
- Bearer token: Authorization: Bearer {access_token}

Protocol: GraphQL only
API Version: 2024-10

Note: Uses Shopify Customer Account API (not Admin API).
Endpoint: https://{shop}/customer/api/{version}/graphql
"""

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional, Tuple
import secrets
import hashlib
import base64
import os
from urllib.parse import urlencode

# Load integration using config.json in the same directory as this file
_config_path = os.path.join(os.path.dirname(__file__), 'config.json')
shopify_customer = Integration.load(_config_path)

# Shopify API version
API_VERSION = "2024-10"


# ============================================================================
# Helper Functions
# ============================================================================

def get_shop_url(context: ExecutionContext) -> str:
    """Extract the shop URL from context credentials."""
    credentials = context.auth.get('credentials', {})
    shop_url = credentials.get('shop_url', '')
    if shop_url:
        shop_url = shop_url.replace('https://', '').replace('http://', '')
        shop_url = shop_url.rstrip('/')
    return shop_url


def get_customer_api_url(context: ExecutionContext) -> str:
    """Build Customer Account API GraphQL endpoint URL.
    
    Uses the correct Customer Account API path: /customer/api/{version}/graphql
    (not /account/customer/api/ which is incorrect)
    """
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/customer/api/{API_VERSION}/graphql"


def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for Customer Account API requests."""
    credentials = context.auth.get('credentials', {})
    access_token = credentials.get('access_token', '')

    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


async def execute_graphql(context: ExecutionContext, query: str,
                          variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute a GraphQL query against the Customer Account API.
    
    Returns the parsed JSON response body.
    """
    url = get_customer_api_url(context)
    headers = build_headers(context)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = await context.fetch(url, method="POST", json=payload, headers=headers)
    
    # Handle response - context.fetch may return dict directly or response object
    if hasattr(response, 'json'):
        # Response object - need to parse JSON
        if callable(response.json):
            import asyncio
            if asyncio.iscoroutinefunction(response.json):
                return await response.json()
            return response.json()
    
    # Already a dict (some SDK versions return parsed JSON directly)
    return response


def success_response(**kwargs) -> ActionResult:
    """Build standardized success response."""
    return ActionResult(data={"success": True, **kwargs}, cost_usd=0.0)


def error_response(message: str, **kwargs) -> ActionResult:
    """Build standardized error response."""
    data = {"success": False, "message": str(message)}
    data.update(kwargs)
    return ActionResult(data=data, cost_usd=0.0)


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
# OAuth Helper Functions
# ============================================================================

def generate_pkce_pair() -> tuple:
    """Generate PKCE code_verifier and code_challenge pair."""
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')
    return code_verifier, code_challenge


def build_authorization_url(shop_url: str, client_id: str, redirect_uri: str,
                            scopes: List[str], state: str,
                            code_challenge: str) -> str:
    """Build Shopify customer authorization URL.
    
    Uses the OIDC-style authorization endpoint for Customer Account API.
    The correct endpoint can be discovered via /.well-known/openid-configuration
    but we use the standard path here for simplicity.
    """
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(scopes),
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    # Use the standard OIDC authorization endpoint
    return f"https://{shop_url}/authentication/oauth/authorize?{urlencode(params)}"


# ============================================================================
# GraphQL Queries
# ============================================================================

QUERY_GET_PROFILE = """
query GetCustomerProfile {
  customer {
    id
    email
    firstName
    lastName
    phone
    acceptsMarketing
    createdAt
    defaultAddress {
      id
      address1
      address2
      city
      province
      provinceCode
      country
      countryCode
      zip
      phone
      company
    }
  }
}
"""

QUERY_LIST_ADDRESSES = """
query ListAddresses($first: Int!, $after: String) {
  customer {
    addresses(first: $first, after: $after) {
      edges {
        cursor
        node {
          id
          address1
          address2
          city
          province
          provinceCode
          country
          countryCode
          zip
          phone
          company
          firstName
          lastName
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
    defaultAddress {
      id
    }
  }
}
"""

QUERY_LIST_ORDERS = """
query ListOrders($first: Int!, $after: String) {
  customer {
    orders(first: $first, after: $after) {
      edges {
        cursor
        node {
          id
          name
          orderNumber
          processedAt
          fulfillmentStatus
          financialStatus
          totalPrice {
            amount
            currencyCode
          }
          subtotal {
            amount
            currencyCode
          }
          totalShipping {
            amount
            currencyCode
          }
          totalTax {
            amount
            currencyCode
          }
          lineItems(first: 10) {
            edges {
              node {
                title
                quantity
                price {
                  amount
                  currencyCode
                }
              }
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
}
"""

QUERY_GET_ORDER = """
query GetOrder($orderId: ID!) {
  customer {
    order(id: $orderId) {
      id
      name
      orderNumber
      processedAt
      fulfillmentStatus
      financialStatus
      totalPrice {
        amount
        currencyCode
      }
      subtotal {
        amount
        currencyCode
      }
      totalShipping {
        amount
        currencyCode
      }
      totalTax {
        amount
        currencyCode
      }
      shippingAddress {
        address1
        address2
        city
        province
        country
        zip
        phone
      }
      billingAddress {
        address1
        address2
        city
        province
        country
        zip
      }
      lineItems(first: 50) {
        edges {
          node {
            title
            quantity
            price {
              amount
              currencyCode
            }
            variant {
              id
              title
              image {
                url
              }
            }
          }
        }
      }
      fulfillments {
        trackingCompany
        trackingNumber
        trackingUrl
        status
      }
    }
  }
}
"""

MUTATION_UPDATE_PROFILE = """
mutation UpdateCustomer($input: CustomerUpdateInput!) {
  customerUpdate(input: $input) {
    customer {
      id
      email
      firstName
      lastName
      phone
      acceptsMarketing
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

MUTATION_CREATE_ADDRESS = """
mutation CreateAddress($address: CustomerAddressInput!) {
  customerAddressCreate(address: $address) {
    customerAddress {
      id
      address1
      address2
      city
      province
      country
      zip
      phone
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

MUTATION_UPDATE_ADDRESS = """
mutation UpdateAddress($addressId: ID!, $address: CustomerAddressInput!) {
  customerAddressUpdate(addressId: $addressId, address: $address) {
    customerAddress {
      id
      address1
      address2
      city
      province
      country
      zip
      phone
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

MUTATION_DELETE_ADDRESS = """
mutation DeleteAddress($addressId: ID!) {
  customerAddressDelete(addressId: $addressId) {
    deletedAddressId
    userErrors {
      field
      message
      code
    }
  }
}
"""

MUTATION_SET_DEFAULT_ADDRESS = """
mutation SetDefaultAddress($addressId: ID!) {
  customerDefaultAddressUpdate(addressId: $addressId) {
    customer {
      defaultAddress {
        id
      }
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""


# ============================================================================
# Profile Actions
# ============================================================================

@shopify_customer.action("customer_get_profile")
class GetProfileHandler(ActionHandler):
    """Get customer's own profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await execute_graphql(context, QUERY_GET_PROFILE)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], customer=None)

            customer = response.get('data', {}).get('customer')
            if not customer:
                return error_response("Customer not found", customer=None)

            return success_response(customer=customer)
        except Exception as e:
            return error_response(e, customer=None)


@shopify_customer.action("customer_update_profile")
class UpdateProfileHandler(ActionHandler):
    """Update customer's profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            customer_input = {}

            # Map input fields to GraphQL input
            field_mapping = {
                'first_name': 'firstName',
                'last_name': 'lastName',
                'phone': 'phone',
                'accepts_marketing': 'acceptsMarketing'
            }

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs:
                    customer_input[graphql_field] = inputs[input_field]

            if not customer_input:
                return error_response("No fields to update", customer=None)

            variables = {"input": customer_input}
            response = await execute_graphql(context, MUTATION_UPDATE_PROFILE, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], customer=None)

            data = response.get('data', {}).get('customerUpdate', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'], customer=None)

            return success_response(customer=data.get('customer'))
        except Exception as e:
            return error_response(e, customer=None)


# ============================================================================
# Address Actions
# ============================================================================

@shopify_customer.action("customer_list_addresses")
class ListAddressesHandler(ActionHandler):
    """List customer's saved addresses."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {
                "first": inputs.get('first', 20),
                "after": inputs.get('after')
            }

            response = await execute_graphql(context, QUERY_LIST_ADDRESSES, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], addresses=[])

            data = response.get('data', {}).get('customer', {})
            addresses = extract_edges(data, 'addresses')
            page_info = data.get('addresses', {}).get('pageInfo', {})
            default_address_id = data.get('defaultAddress', {}).get('id') if data.get('defaultAddress') else None

            # Mark default address
            for addr in addresses:
                addr['isDefault'] = addr.get('id') == default_address_id

            return success_response(
                addresses=addresses,
                count=len(addresses),
                has_next_page=page_info.get('hasNextPage', False),
                end_cursor=page_info.get('endCursor'),
                default_address_id=default_address_id
            )
        except Exception as e:
            return error_response(e, addresses=[], count=0)


@shopify_customer.action("customer_create_address")
class CreateAddressHandler(ActionHandler):
    """Create a new address."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_input = {}

            field_mapping = {
                'address1': 'address1',
                'address2': 'address2',
                'city': 'city',
                'province': 'province',
                'country': 'country',
                'zip': 'zip',
                'phone': 'phone',
                'company': 'company',
                'first_name': 'firstName',
                'last_name': 'lastName'
            }

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs and inputs[input_field]:
                    address_input[graphql_field] = inputs[input_field]

            variables = {"address": address_input}
            response = await execute_graphql(context, MUTATION_CREATE_ADDRESS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], address=None)

            data = response.get('data', {}).get('customerAddressCreate', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'], address=None)

            return success_response(address=data.get('customerAddress'))
        except Exception as e:
            return error_response(e, address=None)


@shopify_customer.action("customer_update_address")
class UpdateAddressHandler(ActionHandler):
    """Update an existing address."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get('address_id')
            if not address_id:
                return error_response("address_id is required", address=None)

            address_input = {}

            field_mapping = {
                'address1': 'address1',
                'address2': 'address2',
                'city': 'city',
                'province': 'province',
                'country': 'country',
                'zip': 'zip',
                'phone': 'phone',
                'company': 'company',
                'first_name': 'firstName',
                'last_name': 'lastName'
            }

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    address_input[graphql_field] = inputs[input_field]

            if not address_input:
                return error_response("No fields to update", address=None)

            variables = {
                "addressId": address_id,
                "address": address_input
            }
            response = await execute_graphql(context, MUTATION_UPDATE_ADDRESS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], address=None)

            data = response.get('data', {}).get('customerAddressUpdate', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'], address=None)

            return success_response(address=data.get('customerAddress'))
        except Exception as e:
            return error_response(e, address=None)


@shopify_customer.action("customer_delete_address")
class DeleteAddressHandler(ActionHandler):
    """Delete an address."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get('address_id')
            if not address_id:
                return error_response("address_id is required")

            variables = {"addressId": address_id}
            response = await execute_graphql(context, MUTATION_DELETE_ADDRESS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'])

            data = response.get('data', {}).get('customerAddressDelete', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'])

            return success_response(
                deleted=True,
                deleted_address_id=data.get('deletedAddressId')
            )
        except Exception as e:
            return error_response(e)


@shopify_customer.action("customer_set_default_address")
class SetDefaultAddressHandler(ActionHandler):
    """Set an address as default."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get('address_id')
            if not address_id:
                return error_response("address_id is required")

            variables = {"addressId": address_id}
            response = await execute_graphql(context, MUTATION_SET_DEFAULT_ADDRESS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'])

            data = response.get('data', {}).get('customerDefaultAddressUpdate', {})
            user_errors = data.get('userErrors', [])

            if user_errors:
                return error_response(user_errors[0]['message'])

            default_id = data.get('customer', {}).get('defaultAddress', {}).get('id')
            return success_response(
                default_address_id=default_id
            )
        except Exception as e:
            return error_response(e)


# ============================================================================
# Order Actions
# ============================================================================

@shopify_customer.action("customer_list_orders")
class ListOrdersHandler(ActionHandler):
    """List customer's orders."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            variables = {
                "first": inputs.get('first', 10),
                "after": inputs.get('after')
            }

            response = await execute_graphql(context, QUERY_LIST_ORDERS, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], orders=[])

            data = response.get('data', {}).get('customer', {})
            orders = extract_edges(data, 'orders')
            page_info = data.get('orders', {}).get('pageInfo', {})

            return success_response(
                orders=orders,
                count=len(orders),
                has_next_page=page_info.get('hasNextPage', False),
                end_cursor=page_info.get('endCursor')
            )
        except Exception as e:
            return error_response(e, orders=[], count=0)


@shopify_customer.action("customer_get_order")
class GetOrderHandler(ActionHandler):
    """Get a specific order by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs.get('order_id')
            if not order_id:
                return error_response("order_id is required", order=None)

            variables = {"orderId": order_id}
            response = await execute_graphql(context, QUERY_GET_ORDER, variables)

            if 'errors' in response:
                return error_response(response['errors'][0]['message'], order=None)

            order = response.get('data', {}).get('customer', {}).get('order')
            if not order:
                return error_response("Order not found", order=None)

            return success_response(order=order)
        except Exception as e:
            return error_response(e, order=None)


# ============================================================================
# OAuth Helper Actions
# ============================================================================

@shopify_customer.action("customer_generate_oauth_url")
class GenerateOAuthUrlHandler(ActionHandler):
    """Generate OAuth authorization URL for customer login."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            shop_url = get_shop_url(context)
            client_id = inputs.get('client_id')
            redirect_uri = inputs.get('redirect_uri')
            # Use OIDC-style scopes for Customer Account API
            scopes = inputs.get('scopes', [
                'openid',
                'email',
                'customer-account-api:full'
            ])

            if not client_id:
                return error_response("client_id is required")
            if not redirect_uri:
                return error_response("redirect_uri is required")

            # Generate PKCE
            code_verifier, code_challenge = generate_pkce_pair()
            state = secrets.token_urlsafe(16)

            # Build URL
            auth_url = build_authorization_url(
                shop_url=shop_url,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scopes=scopes,
                state=state,
                code_challenge=code_challenge
            )

            return success_response(
                authorization_url=auth_url,
                code_verifier=code_verifier,  # Store this securely!
                state=state  # Verify this on callback
            )
        except Exception as e:
            return error_response(e)


@shopify_customer.action("customer_exchange_code")
class ExchangeCodeHandler(ActionHandler):
    """Exchange authorization code for tokens."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            shop_url = get_shop_url(context)
            code = inputs.get('code')
            code_verifier = inputs.get('code_verifier')
            redirect_uri = inputs.get('redirect_uri')
            client_id = inputs.get('client_id')

            if not all([code, code_verifier, redirect_uri, client_id]):
                return error_response("code, code_verifier, redirect_uri, and client_id are required")

            # Use the standard OIDC token endpoint
            url = f"https://{shop_url}/authentication/oauth/token"
            data = {
                'client_id': client_id,
                'code': code,
                'redirect_uri': redirect_uri,
                'code_verifier': code_verifier,
                'grant_type': 'authorization_code'
            }

            response = await context.fetch(
                url,
                method="POST",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Handle response object if needed
            if hasattr(response, 'json'):
                if callable(response.json):
                    import asyncio
                    if asyncio.iscoroutinefunction(response.json):
                        response = await response.json()
                    else:
                        response = response.json()

            if 'error' in response:
                return error_response(response.get('error_description', response['error']))

            return success_response(
                access_token=response.get('access_token'),
                refresh_token=response.get('refresh_token'),
                id_token=response.get('id_token'),
                token_type=response.get('token_type'),
                expires_in=response.get('expires_in'),
                scope=response.get('scope')
            )
        except Exception as e:
            return error_response(e)


@shopify_customer.action("customer_refresh_token")
class RefreshTokenHandler(ActionHandler):
    """Refresh access token using refresh token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            shop_url = get_shop_url(context)
            refresh_token = inputs.get('refresh_token')
            client_id = inputs.get('client_id')

            if not refresh_token:
                return error_response("refresh_token is required")
            if not client_id:
                return error_response("client_id is required")

            # Use the standard OIDC token endpoint
            url = f"https://{shop_url}/authentication/oauth/token"
            data = {
                'client_id': client_id,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }

            response = await context.fetch(
                url,
                method="POST",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Handle response object if needed
            if hasattr(response, 'json'):
                if callable(response.json):
                    import asyncio
                    if asyncio.iscoroutinefunction(response.json):
                        response = await response.json()
                    else:
                        response = response.json()

            if 'error' in response:
                return error_response(response.get('error_description', response['error']))

            return success_response(
                access_token=response.get('access_token'),
                refresh_token=response.get('refresh_token'),
                token_type=response.get('token_type'),
                expires_in=response.get('expires_in')
            )
        except Exception as e:
            return error_response(e)
