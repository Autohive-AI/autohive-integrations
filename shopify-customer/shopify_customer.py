"""
Shopify Customer Account API Integration
========================================

Provides access to Shopify's Customer Account API for customer self-service.

Supported Operations:
- Profile: get, update
- Addresses: list, create, update, delete, set default
- Orders: list, get

Authentication:
- Custom auth with a Shopify customer access token
- OAuth 2.0 + PKCE helper actions for obtaining customer access tokens
- Header: Authorization: {access_token}

Protocol: GraphQL only
API Version: 2026-10

Note: Uses Shopify Customer Account API (not Admin API).
Endpoint: https://{shop}/customer/api/{version}/graphql
"""

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
import base64
import hashlib
import re
import secrets
from typing import Any, Dict, List
from urllib.parse import urlencode

# Load integration using config.json in the same directory as this file
shopify_customer = Integration.load()

# Shopify API version
API_VERSION = "2026-10"
SHOP_DOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$", re.IGNORECASE)
DEFAULT_SCOPES = ["openid", "email", "customer-account-api:full"]


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


def get_customer_api_url(context: ExecutionContext) -> str:
    """Build Customer Account API GraphQL endpoint URL.

    Uses the correct Customer Account API path: /customer/api/{version}/graphql
    (not /account/customer/api/ which is incorrect)
    """
    shop_url = get_shop_url(context)
    return f"https://{shop_url}/customer/api/{API_VERSION}/graphql"


def build_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for Customer Account API requests."""
    access_token = str(get_credentials(context).get("access_token", "")).strip()
    if not access_token:
        raise ValueError("Missing Shopify customer access token")

    return {
        "Authorization": access_token,
        "Content-Type": "application/json",
    }


async def execute_graphql(context: ExecutionContext, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute a GraphQL query against the Customer Account API.

    Returns the parsed JSON response body.
    """
    url = get_customer_api_url(context)
    headers = build_headers(context)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = await context.fetch(url, method="POST", json=payload, headers=headers)
    return response.data


def success_response(**kwargs) -> ActionResult:
    """Build standardized success response."""
    return ActionResult(data={"success": True, **kwargs}, cost_usd=0.0)


def error_response(message, **kwargs):
    """Return an ActionError."""
    return ActionError(message=str(message))


def extract_edges(data: Dict, path: str) -> List[Dict]:
    """Extract nodes from GraphQL edges structure."""
    parts = path.split(".")
    current = data
    for part in parts:
        if current is None:
            return []
        current = current.get(part)
    if current and "edges" in current:
        return [edge["node"] for edge in current["edges"]]
    return []


# ============================================================================
# OAuth Helper Functions
# ============================================================================


def generate_pkce_pair() -> tuple:
    """Generate PKCE code_verifier and code_challenge pair."""
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    return code_verifier, code_challenge


def build_authorization_url(
    shop_url: str,
    client_id: str,
    redirect_uri: str,
    scopes: List[str],
    state: str,
    code_challenge: str,
) -> str:
    """Build Shopify customer authorization URL.

    Uses the OIDC-style authorization endpoint for Customer Account API.
    The correct endpoint can be discovered via /.well-known/openid-configuration
    but we use the standard path here for simplicity.
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    # Use the standard OIDC authorization endpoint
    return f"https://{shop_url}/authentication/oauth/authorize?{urlencode(params)}"


def get_client_id(context: ExecutionContext) -> str:
    """Return the configured Customer Account API client ID."""
    client_id = str(get_credentials(context).get("client_id", "")).strip()
    if not client_id:
        raise ValueError("Missing Shopify Customer Account API client ID")
    return client_id


def build_token_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build token endpoint headers for public or confidential clients."""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    client_secret = str(get_credentials(context).get("client_secret", "")).strip()
    if client_secret:
        credentials = f"{get_client_id(context)}:{client_secret}".encode()
        headers["Authorization"] = f"Basic {base64.b64encode(credentials).decode()}"
    return headers


# ============================================================================
# GraphQL Queries
# ============================================================================

QUERY_GET_PROFILE = """
query GetCustomerProfile {
  customer {
    id
    emailAddress {
      emailAddress
      marketingState
    }
    firstName
    lastName
    phoneNumber {
      phoneNumber
    }
    creationDate
    defaultAddress {
      id
      address1
      address2
      city
      province
      zoneCode
      country
      countryCode
      zip
      phoneNumber
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
          zoneCode
          country
          countryCode
          zip
          phoneNumber
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
          number
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
                name
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
  order(id: $orderId) {
    id
    name
    number
    processedAt
    fulfillmentStatus
    financialStatus
    totalPrice { amount currencyCode }
    subtotal { amount currencyCode }
    totalShipping { amount currencyCode }
    totalTax { amount currencyCode }
    shippingAddress {
      address1
      address2
      city
      province
      country
      zip
      phoneNumber
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
          name
          quantity
          price { amount currencyCode }
          variantId
          variantTitle
          image { url }
        }
      }
    }
    fulfillments(first: 50) {
      edges {
        node {
          id
          status
          latestShipmentStatus
          trackingInformation { company number url }
        }
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
      emailAddress {
        emailAddress
        marketingState
      }
      firstName
      lastName
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

MUTATION_SUBSCRIBE_MARKETING = """
mutation SubscribeToEmailMarketing {
  customerEmailMarketingSubscribe {
    emailAddress { emailAddress marketingState }
    userErrors { field message code }
  }
}
"""

MUTATION_UNSUBSCRIBE_MARKETING = """
mutation UnsubscribeFromEmailMarketing {
  customerEmailMarketingUnsubscribe {
    emailAddress { emailAddress marketingState }
    userErrors { field message code }
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
      zoneCode
      country
      countryCode
      zip
      phoneNumber
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
      zoneCode
      country
      countryCode
      zip
      phoneNumber
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
  customerAddressUpdate(addressId: $addressId, defaultAddress: true) {
    customerAddress { id }
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
            gql_result = await execute_graphql(context, QUERY_GET_PROFILE)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], customer=None)

            customer = gql_result.get("data", {}).get("customer")
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
            field_mapping = {"first_name": "firstName", "last_name": "lastName"}

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs:
                    customer_input[graphql_field] = inputs[input_field]

            marketing_preference = inputs.get("accepts_marketing")
            if not customer_input and marketing_preference is None:
                return error_response("No fields to update", customer=None)

            customer = None
            if customer_input:
                variables = {"input": customer_input}
                gql_result = await execute_graphql(context, MUTATION_UPDATE_PROFILE, variables)
                if "errors" in gql_result:
                    return error_response(gql_result["errors"][0]["message"], customer=None)

                data = gql_result.get("data", {}).get("customerUpdate", {})
                user_errors = data.get("userErrors", [])
                if user_errors:
                    return error_response(user_errors[0]["message"], customer=None)
                customer = data.get("customer")

            if marketing_preference is not None:
                mutation = MUTATION_SUBSCRIBE_MARKETING if marketing_preference else MUTATION_UNSUBSCRIBE_MARKETING
                mutation_key = (
                    "customerEmailMarketingSubscribe" if marketing_preference else "customerEmailMarketingUnsubscribe"
                )
                gql_result = await execute_graphql(context, mutation)
                if "errors" in gql_result:
                    return error_response(gql_result["errors"][0]["message"], customer=customer)

                marketing_data = gql_result.get("data", {}).get(mutation_key, {})
                user_errors = marketing_data.get("userErrors", [])
                if user_errors:
                    return error_response(user_errors[0]["message"], customer=customer)

                email_address = marketing_data.get("emailAddress")
                if customer is None:
                    customer = {"emailAddress": email_address}
                else:
                    customer["emailAddress"] = email_address

            return success_response(customer=customer)
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
            variables = {"first": inputs.get("first", 20), "after": inputs.get("after")}

            gql_result = await execute_graphql(context, QUERY_LIST_ADDRESSES, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], addresses=[])

            data = gql_result.get("data", {}).get("customer", {})
            addresses = extract_edges(data, "addresses")
            page_info = data.get("addresses", {}).get("pageInfo", {})
            default_address_id = data.get("defaultAddress", {}).get("id") if data.get("defaultAddress") else None

            # Mark default address
            for addr in addresses:
                addr["isDefault"] = addr.get("id") == default_address_id

            return success_response(
                addresses=addresses,
                count=len(addresses),
                has_next_page=page_info.get("hasNextPage", False),
                end_cursor=page_info.get("endCursor"),
                default_address_id=default_address_id,
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
                "address1": "address1",
                "address2": "address2",
                "city": "city",
                "province": "zoneCode",
                "country": "countryCode",
                "zip": "zip",
                "phone": "phoneNumber",
                "company": "company",
                "first_name": "firstName",
                "last_name": "lastName",
            }

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs and inputs[input_field]:
                    address_input[graphql_field] = inputs[input_field]

            variables = {"address": address_input}
            gql_result = await execute_graphql(context, MUTATION_CREATE_ADDRESS, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], address=None)

            data = gql_result.get("data", {}).get("customerAddressCreate", {})
            user_errors = data.get("userErrors", [])

            if user_errors:
                return error_response(user_errors[0]["message"], address=None)

            return success_response(address=data.get("customerAddress"))
        except Exception as e:
            return error_response(e, address=None)


@shopify_customer.action("customer_update_address")
class UpdateAddressHandler(ActionHandler):
    """Update an existing address."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get("address_id")
            if not address_id:
                return error_response("address_id is required", address=None)

            address_input = {}

            field_mapping = {
                "address1": "address1",
                "address2": "address2",
                "city": "city",
                "province": "zoneCode",
                "country": "countryCode",
                "zip": "zip",
                "phone": "phoneNumber",
                "company": "company",
                "first_name": "firstName",
                "last_name": "lastName",
            }

            for input_field, graphql_field in field_mapping.items():
                if input_field in inputs and inputs[input_field] is not None:
                    address_input[graphql_field] = inputs[input_field]

            if not address_input:
                return error_response("No fields to update", address=None)

            variables = {"addressId": address_id, "address": address_input}
            gql_result = await execute_graphql(context, MUTATION_UPDATE_ADDRESS, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], address=None)

            data = gql_result.get("data", {}).get("customerAddressUpdate", {})
            user_errors = data.get("userErrors", [])

            if user_errors:
                return error_response(user_errors[0]["message"], address=None)

            return success_response(address=data.get("customerAddress"))
        except Exception as e:
            return error_response(e, address=None)


@shopify_customer.action("customer_delete_address")
class DeleteAddressHandler(ActionHandler):
    """Delete an address."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get("address_id")
            if not address_id:
                return error_response("address_id is required")

            variables = {"addressId": address_id}
            gql_result = await execute_graphql(context, MUTATION_DELETE_ADDRESS, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"])

            data = gql_result.get("data", {}).get("customerAddressDelete", {})
            user_errors = data.get("userErrors", [])

            if user_errors:
                return error_response(user_errors[0]["message"])

            return success_response(deleted=True, deleted_address_id=data.get("deletedAddressId"))
        except Exception as e:
            return error_response(e)


@shopify_customer.action("customer_set_default_address")
class SetDefaultAddressHandler(ActionHandler):
    """Set an address as default."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            address_id = inputs.get("address_id")
            if not address_id:
                return error_response("address_id is required")

            variables = {"addressId": address_id}
            gql_result = await execute_graphql(context, MUTATION_SET_DEFAULT_ADDRESS, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"])

            data = gql_result.get("data", {}).get("customerAddressUpdate", {})
            user_errors = data.get("userErrors", [])

            if user_errors:
                return error_response(user_errors[0]["message"])

            default_id = (data.get("customerAddress") or {}).get("id")
            return success_response(default_address_id=default_id)
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
            variables = {"first": inputs.get("first", 10), "after": inputs.get("after")}

            gql_result = await execute_graphql(context, QUERY_LIST_ORDERS, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], orders=[])

            data = gql_result.get("data", {}).get("customer", {})
            orders = extract_edges(data, "orders")
            page_info = data.get("orders", {}).get("pageInfo", {})

            return success_response(
                orders=orders,
                count=len(orders),
                has_next_page=page_info.get("hasNextPage", False),
                end_cursor=page_info.get("endCursor"),
            )
        except Exception as e:
            return error_response(e, orders=[], count=0)


@shopify_customer.action("customer_get_order")
class GetOrderHandler(ActionHandler):
    """Get a specific order by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            order_id = inputs.get("order_id")
            if not order_id:
                return error_response("order_id is required", order=None)

            variables = {"orderId": order_id}
            gql_result = await execute_graphql(context, QUERY_GET_ORDER, variables)

            if "errors" in gql_result:
                return error_response(gql_result["errors"][0]["message"], order=None)

            order = gql_result.get("data", {}).get("order")
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
            client_id = get_client_id(context)
            redirect_uri = inputs.get("redirect_uri")
            scopes = inputs.get("scopes", DEFAULT_SCOPES)

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
                code_challenge=code_challenge,
            )

            return success_response(
                authorization_url=auth_url,
                code_verifier=code_verifier,  # Store this securely!
                state=state,  # Verify this on callback
            )
        except Exception as e:
            return error_response(e)


@shopify_customer.action("customer_exchange_code")
class ExchangeCodeHandler(ActionHandler):
    """Exchange authorization code for tokens."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            shop_url = get_shop_url(context)
            code = inputs.get("code")
            code_verifier = inputs.get("code_verifier")
            redirect_uri = inputs.get("redirect_uri")
            client_id = get_client_id(context)

            if not all([code, redirect_uri]):
                return error_response("code and redirect_uri are required")
            if not code_verifier and not get_credentials(context).get("client_secret"):
                return error_response("code_verifier is required for public clients")

            # Use the standard OIDC token endpoint
            url = f"https://{shop_url}/authentication/oauth/token"
            data = {
                "client_id": client_id,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            if code_verifier:
                data["code_verifier"] = code_verifier

            response = await context.fetch(
                url,
                method="POST",
                data=data,
                headers=build_token_headers(context),
            )

            token_data = response.data

            if "error" in token_data:
                return ActionError(message=token_data.get("error_description", token_data["error"]))

            token_result = {
                key: token_data.get(key)
                for key in ("access_token", "refresh_token", "id_token", "token_type", "expires_in", "scope")
                if token_data.get(key) is not None
            }
            return success_response(**token_result)
        except Exception as e:
            return ActionError(message=str(e))


@shopify_customer.action("customer_refresh_token")
class RefreshTokenHandler(ActionHandler):
    """Refresh access token using refresh token."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            shop_url = get_shop_url(context)
            refresh_token = inputs.get("refresh_token")
            client_id = get_client_id(context)

            if not refresh_token:
                return error_response("refresh_token is required")
            # Use the standard OIDC token endpoint
            url = f"https://{shop_url}/authentication/oauth/token"
            data = {
                "client_id": client_id,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            response = await context.fetch(
                url,
                method="POST",
                data=data,
                headers=build_token_headers(context),
            )

            token_data = response.data

            if "error" in token_data:
                return ActionError(message=token_data.get("error_description", token_data["error"]))

            token_result = {
                key: token_data.get(key)
                for key in ("access_token", "refresh_token", "token_type", "expires_in")
                if token_data.get(key) is not None
            }
            return success_response(**token_result)
        except Exception as e:
            return ActionError(message=str(e))
