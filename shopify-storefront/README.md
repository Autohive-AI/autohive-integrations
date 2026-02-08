# Shopify Storefront Integration for Autohive

Connects Autohive to the Shopify Storefront API to manage customer-facing e-commerce operations including products, collections, carts, and customer accounts.

## Description

This integration provides access to the Shopify Storefront API (GraphQL), allowing you to build custom storefront experiences or automate customer-facing actions. Key features include:

- **Products**: List, search, and retrieve product details
- **Collections**: Browse product collections
- **Cart Management**: Create carts, manage line items, and apply discounts
- **Customer Accounts**: Create customers, handle login, retrieve profiles, and recover passwords

## Setup & Authentication

This integration uses **Platform Authentication** with Shopify.

**Scopes Required:**
- `unauthenticated_read_product_listings`
- `unauthenticated_read_product_inventory`
- `unauthenticated_read_checkouts`
- `unauthenticated_write_checkouts`
- `unauthenticated_read_customers`
- `unauthenticated_write_customers`

## Actions

### Product Actions

#### `storefront_list_products`
Browse products available in the storefront with pagination and filtering.

**Inputs:**
- `first` (integer, optional): Number of products to return (default: 20)
- `after` (string, optional): Cursor for pagination
- `query` (string, optional): Filter query (e.g., 'title:*shirt*' or 'tag:sale')

**Outputs:**
- `products` (array): List of products
- `count` (integer): Number of products returned
- `has_next_page` (boolean): Whether there are more pages
- `end_cursor` (string): Cursor for the next page
- `success` (boolean)

---

#### `storefront_get_product`
Get detailed product information by handle or ID.

**Inputs:**
- `handle` (string, optional): Product handle (URL slug)
- `product_id` (string, optional): Product GraphQL ID

**Outputs:**
- `product` (object): Product details
- `success` (boolean)

---

#### `storefront_search_products`
Search products by keyword.

**Inputs:**
- `query` (string, required): Search query
- `first` (integer, optional): Number of results (default: 20)

**Outputs:**
- `products` (array): List of matching products
- `count` (integer): Number of products returned
- `total_count` (integer): Total number of matches
- `success` (boolean)

---

### Collection Actions

#### `storefront_list_collections`
Browse product collections in the storefront.

**Inputs:**
- `first` (integer, optional): Number of collections to return (default: 20)
- `after` (string, optional): Cursor for pagination

**Outputs:**
- `collections` (array): List of collections
- `count` (integer): Number of collections returned
- `has_next_page` (boolean): Whether there are more pages
- `end_cursor` (string): Cursor for the next page
- `success` (boolean)

---

#### `storefront_get_collection`
Get collection details with products.

**Inputs:**
- `handle` (string, optional): Collection handle
- `collection_id` (string, optional): Collection GraphQL ID
- `products_first` (integer, optional): Number of products to include (default: 20)

**Outputs:**
- `collection` (object): Collection details with products
- `success` (boolean)

---

### Cart Actions

#### `storefront_create_cart`
Create a new shopping cart, optionally with initial items.

**Inputs:**
- `lines` (array, optional): Initial cart items `[{merchandiseId, quantity}]`
- `buyer_identity` (object, optional): Buyer info `{email, countryCode}`

**Outputs:**
- `cart` (object): Created cart details
- `success` (boolean)

---

#### `storefront_get_cart`
Retrieve cart contents and checkout URL.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID

**Outputs:**
- `cart` (object): Cart details
- `success` (boolean)

---

#### `storefront_add_to_cart`
Add items to an existing cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `lines` (array, required): Items to add `[{merchandiseId, quantity}]`

**Outputs:**
- `cart` (object): Updated cart details
- `success` (boolean)

---

#### `storefront_update_cart_line`
Update quantity of items in cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `lines` (array, required): Lines to update `[{id, quantity}]`

**Outputs:**
- `cart` (object): Updated cart details
- `success` (boolean)

---

#### `storefront_remove_from_cart`
Remove items from cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `line_ids` (array, required): List of line IDs to remove

**Outputs:**
- `cart` (object): Updated cart details
- `success` (boolean)

---

#### `storefront_apply_discount`
Apply discount codes to cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `discount_codes` (array, required): List of discount codes to apply

**Outputs:**
- `cart` (object): Updated cart details
- `success` (boolean)

---

### Customer Actions

#### `storefront_create_customer`
Create a new customer account.

**Inputs:**
- `email` (string, required): Customer email
- `password` (string, required): Account password
- `first_name` (string, optional)
- `last_name` (string, optional)
- `phone` (string, optional)
- `accepts_marketing` (boolean, optional)

**Outputs:**
- `customer` (object): Created customer details
- `success` (boolean)

---

#### `storefront_customer_login`
Login customer and get access token.

**Inputs:**
- `email` (string, required): Customer email
- `password` (string, required): Password

**Outputs:**
- `customer_access_token` (string): Access token for subsequent requests
- `expires_at` (string): Token expiration time
- `success` (boolean)

---

#### `storefront_get_customer`
Get customer profile using access token.

**Inputs:**
- `customer_access_token` (string, required): Token from login

**Outputs:**
- `customer` (object): Customer profile
- `success` (boolean)

---

#### `storefront_recover_customer`
Send password recovery email.

**Inputs:**
- `email` (string, required): Customer email

**Outputs:**
- `message` (string): Status message
- `success` (boolean)

---

#### `storefront_update_customer`
Update customer profile using access token.

**Inputs:**
- `customer_access_token` (string, required): Token from login
- `first_name` (string, optional)
- `last_name` (string, optional)
- `email` (string, optional): New email address
- `phone` (string, optional)
- `password` (string, optional): New password
- `accepts_marketing` (boolean, optional)

**Outputs:**
- `customer` (object): Updated customer profile
- `customer_access_token` (string): New access token (if credentials changed)
- `expires_at` (string): Token expiration time
- `success` (boolean)

## Requirements

- `autohive-integrations-sdk`
- `aiohttp`

## Usage Examples

### Example 1: Search Products
```python
result = await shopify_storefront.execute_action("storefront_search_products", {
    "query": "t-shirt",
    "first": 5
}, context)

for product in result.data["products"]:
    print(f"Found: {product['title']} - {product['id']}")
```

### Example 2: Create Cart and Add Item
```python
# 1. Create a cart
cart_result = await shopify_storefront.execute_action("storefront_create_cart", {}, context)
cart_id = cart_result.data["cart"]["id"]

# 2. Add item to cart
# Assuming you have a product variant ID
variant_id = "gid://shopify/ProductVariant/1234567890"

await shopify_storefront.execute_action("storefront_add_to_cart", {
    "cart_id": cart_id,
    "lines": [
        {
            "merchandiseId": variant_id,
            "quantity": 1
        }
    ]
}, context)
```

### Example 3: Customer Login and Profile
```python
# 1. Login
login_result = await shopify_storefront.execute_action("storefront_customer_login", {
    "email": "customer@example.com",
    "password": "securepassword123"
}, context)

token = login_result.data["customer_access_token"]

# 2. Get Profile
profile = await shopify_storefront.execute_action("storefront_get_customer", {
    "customer_access_token": token
}, context)

print(f"Logged in as: {profile.data['customer']['firstName']}")
```

## Testing

To run the tests:

1. Navigate to the integration's directory:
   ```bash
   cd shopify-storefront
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the tests:
   ```bash
   python -m pytest tests/
   ```
