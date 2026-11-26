# Shopify Customer Account Integration for Autohive

Connects Autohive to the Shopify Customer Account API, allowing for customer self-service operations such as managing profiles, addresses, and viewing order history.

## Description

This integration facilitates interaction with Shopify's Customer Account API (GraphQL). It is designed to be used in contexts where a customer is authenticated (e.g., a customer portal), allowing them to manage their own data.

Key capabilities:
- **Profile Management**: View and update personal information.
- **Address Book**: List, create, update, delete, and set default addresses.
- **Order History**: View past orders and order details.
- **Authentication**: Helper actions for implementing OAuth 2.0 with PKCE flow.

## Setup & Authentication

This integration uses **OAuth 2.0 with PKCE** (Proof Key for Code Exchange) as it acts on behalf of a specific customer.

**Scopes Required (OIDC-style for Customer Account API):**
- `openid`
- `email`
- `customer-account-api:full`

### OAuth Flow Implementation
Since this integration runs on behalf of a customer, you will typically need to:
1. Use `customer_generate_oauth_url` to get the login URL and `code_verifier`.
2. Redirect the user to the `authorization_url`.
3. Handle the callback to get the `code`.
4. Use `customer_exchange_code` with the `code` and `code_verifier` to get tokens.
5. Use `customer_refresh_token` to maintain access when the token expires.

## Actions

### Profile Actions

#### `customer_get_profile`
Get the authenticated customer's profile.

**Inputs:**
*None*

**Outputs:**
- `customer` (object): Customer details (name, email, phone, etc.)
- `success` (boolean)

---

#### `customer_update_profile`
Update the customer's profile information.

**Inputs:**
- `first_name` (string, optional)
- `last_name` (string, optional)
- `phone` (string, optional)
- `accepts_marketing` (boolean, optional)

**Outputs:**
- `customer` (object): Updated customer details
- `success` (boolean)

---

### Address Actions

#### `customer_list_addresses`
List the customer's saved addresses.

**Inputs:**
- `first` (integer, optional): Number of addresses to return (default: 20)
- `after` (string, optional): Pagination cursor

**Outputs:**
- `addresses` (array): List of address objects
- `count` (integer)
- `default_address_id` (string): ID of the default address
- `success` (boolean)

---

#### `customer_create_address`
Add a new address to the customer's account.

**Inputs:**
- `address1` (string, required)
- `city` (string, required)
- `country` (string, required): Country code (e.g., US)
- `zip` (string, required)
- `address2` (string, optional)
- `province` (string, optional)
- `first_name`, `last_name`, `company`, `phone` (optional)

**Outputs:**
- `address` (object): Created address details
- `success` (boolean)

---

#### `customer_update_address`
Update an existing address.

**Inputs:**
- `address_id` (string, required): The GraphQL ID of the address
- `address1`, `city`, `country`, `zip`, etc. (optional fields to update)

**Outputs:**
- `address` (object): Updated address details
- `success` (boolean)

---

#### `customer_delete_address`
Remove an address from the account.

**Inputs:**
- `address_id` (string, required)

**Outputs:**
- `deleted_address_id` (string)
- `success` (boolean)

---

#### `customer_set_default_address`
Set a specific address as the default for the account.

**Inputs:**
- `address_id` (string, required)

**Outputs:**
- `default_address_id` (string)
- `success` (boolean)

---

### Order Actions

#### `customer_list_orders`
List the customer's order history.

**Inputs:**
- `first` (integer, optional): Default 10
- `after` (string, optional)

**Outputs:**
- `orders` (array): List of orders with summary info
- `success` (boolean)

---

#### `customer_get_order`
Get detailed information about a specific order.

**Inputs:**
- `order_id` (string, required)

**Outputs:**
- `order` (object): Detailed order info including line items and shipping addresses
- `success` (boolean)

---

### OAuth Helper Actions

#### `customer_generate_oauth_url`
Generate the URL to redirect the user to for login, along with PKCE values.

**Inputs:**
- `client_id` (string, required)
- `redirect_uri` (string, required)
- `scopes` (array, optional): Default scopes provided if omitted

**Outputs:**
- `authorization_url` (string): Redirect the user here
- `code_verifier` (string): **Save this**, it is needed for the token exchange
- `state` (string): Used for CSRF protection
- `success` (boolean)

---

#### `customer_exchange_code`
Exchange the auth code received in the callback for access tokens.

**Inputs:**
- `code` (string, required): From the callback URL
- `code_verifier` (string, required): Generated in the previous step
- `redirect_uri` (string, required)
- `client_id` (string, required)

**Outputs:**
- `access_token` (string)
- `refresh_token` (string)
- `expires_in` (integer)
- `success` (boolean)

---

#### `customer_refresh_token`
Get a fresh access token using a refresh token.

**Inputs:**
- `refresh_token` (string, required)
- `client_id` (string, required)

**Outputs:**
- `access_token` (string)
- `refresh_token` (string): Optionally a new refresh token
- `expires_in` (integer)
- `success` (boolean)

## Requirements

- `autohive-integrations-sdk`

## Usage Examples

Run these fragments inside an async function with the registered `shopify_customer` instance from `shopify_customer.py`. Import `ResultType` from `autohive_integrations_sdk`. Your caller must supply an open `ExecutionContext` named `context`, managed with `async with`, using `{"auth_type": "Custom", "credentials": {"shop_url": supplied_shop_domain, "access_token": supplied_customer_token}}`. OAuth URL generation and code exchange need the shop domain but don't need an access token yet. Profile, order, and address actions need the customer's token; these handlers construct the Bearer header themselves.

`execute_action` returns an `IntegrationResult`. Check `ResultType.ACTION` before reading `result.result.data`; handle other result types as failures. See the [SDK calling patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md). These examples don't change [requirements.txt](requirements.txt). Replace placeholder IDs and OAuth values with values supplied securely by your caller; don't embed live credentials in source.

### Example 1: OAuth Flow (Simplified)
```python
# 1. Generate URL
auth_data = await shopify_customer.execute_action(
    "customer_generate_oauth_url",
    {"client_id": "your_client_id", "redirect_uri": "https://yourapp.com/callback"},
    context,
)
assert auth_data.type == ResultType.ACTION, auth_data.result

# Redirect to auth_data.result.data["authorization_url"]. Store the state and
# code_verifier securely. Verify the callback state before exchanging its code.

# 2. Exchange Code
tokens = await shopify_customer.execute_action(
    "customer_exchange_code",
    {
        "code": "received_auth_code",
        "code_verifier": auth_data.result.data["code_verifier"],
        "redirect_uri": "https://yourapp.com/callback",
        "client_id": "your_client_id",
    },
    context,
)
assert tokens.type == ResultType.ACTION, tokens.result

# Store tokens.result.data["access_token"] securely and supply it as
# context.auth["credentials"]["access_token"] for subsequent authenticated calls.
```

### Example 2: List Orders
```python
result = await shopify_customer.execute_action("customer_list_orders", {"first": 5}, context)

assert result.type == ResultType.ACTION, result.result
for order in result.result.data["orders"]:
    print(f"Order {order['orderNumber']} - {order['totalPrice']['amount']} {order['totalPrice']['currencyCode']}")
```

### Example 3: Update Default Address
```python
# Create new address
new_addr = await shopify_customer.execute_action(
    "customer_create_address",
    {"address1": "123 New St", "city": "New York", "province": "NY", "country": "US", "zip": "10001"},
    context,
)
assert new_addr.type == ResultType.ACTION, new_addr.result

# Set as default
default_result = await shopify_customer.execute_action(
    "customer_set_default_address", {"address_id": new_addr.result.data["address"]["id"]}, context
)
assert default_result.type == ResultType.ACTION, default_result.result
```

## Testing

Install HiveUp 2.5.4 from a Tooling local build as described in the root [contribution guide](../CONTRIBUTING.md). HiveUp isn't published to PyPI and isolates this integration's existing requirements. From the repository root, run the offline unit tests:

```bash
hiveup test shopify-customer
```
