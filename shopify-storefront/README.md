# Shopify Storefront Integration for Autohive

Connects Autohive to the Shopify Storefront API to manage customer-facing e-commerce operations including products, collections, carts, and customer accounts.

## Description

This integration provides access to the Shopify Storefront API (GraphQL), allowing you to build custom storefront experiences or automate customer-facing actions. Key features include:

- **Products**: List, search, and retrieve product details
- **Collections**: Browse product collections
- **Cart Management**: Create carts, manage line items, apply discounts and gift cards, set the buyer, notes and custom attributes
- **Customer Accounts**: Create customers, log in and out, renew tokens, retrieve profiles, and recover passwords
- **Store Content**: Shop policies, pages, blog articles, and navigation menus
- **Product Discovery**: Product recommendations and search-as-you-type suggestions

## Setup & Authentication

This integration uses **custom authentication** with a Storefront API token from the store's Headless channel.

1. In Shopify admin, install the [Headless](https://apps.shopify.com/headless) sales channel and create a storefront.
2. Open **Sales channels > Headless > your storefront > Manage API access**, then click **Manage** for the Storefront API.
3. Enable the Storefront API permissions this integration needs:
   - Products, collections and inventory (read)
   - Carts/checkouts (read and write)
   - Customers (read and write)
   - Content: pages, blogs and articles, and navigation menus (read)
4. In Autohive, add the Shopify Storefront integration and enter:
   - **Shop domain** — the store's permanent domain, such as `your-store.myshopify.com`
   - **Public access token**, or a **Private access token** for server-side use (the private token is used when both are set)
   - **Buyer IP** (optional) — only sent with private-token requests. It is set once for the connection, so it is not each shopper's own IP

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
- `lines` (array, optional): Initial cart items `[{merchandiseId, quantity}]`; `quantity` is optional and defaults to 1
- `buyer_identity` (object, optional): Buyer info `{email, countryCode}`

**Outputs:**
- `cart` (object): Created cart details
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request, e.g. `MERCHANDISE_OUT_OF_STOCK` or `MERCHANDISE_NOT_ENOUGH_STOCK` when a quantity was lowered
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
- `lines` (array, required): Items to add `[{merchandiseId, quantity}]`; `quantity` is optional and defaults to 1

**Outputs:**
- `cart` (object): Updated cart details
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request, e.g. `MERCHANDISE_OUT_OF_STOCK` or `MERCHANDISE_NOT_ENOUGH_STOCK` when a quantity was lowered
- `success` (boolean)

---

#### `storefront_update_cart_line`
Update quantity of items in cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `lines` (array, required): Lines to update `[{id, quantity}]`; only `id` is required

**Outputs:**
- `cart` (object): Updated cart details
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request, e.g. `MERCHANDISE_OUT_OF_STOCK` or `MERCHANDISE_NOT_ENOUGH_STOCK` when a quantity was lowered
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
Apply discount codes to cart. The list replaces any codes already applied; pass an empty list to remove all codes.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `discount_codes` (array, required): List of discount codes to apply, or `[]` to clear them

**Outputs:**
- `cart` (object): Updated cart details
- `success` (boolean)

---

#### `storefront_update_cart_buyer_identity`
Link a cart to a logged-in customer, or set the buyer's email, phone or country. The country controls local pricing and availability. A linked customer's details carry through to checkout, but with a private token Shopify only keeps them logged in at checkout when the request carries the buyer's IP, so they may be asked to log in again.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `customer_access_token` (string, optional): Token from `storefront_customer_login`
- `email` (string, optional): Buyer email
- `phone` (string, optional): Buyer phone in E.164 format
- `country_code` (string, optional): Two-letter country code, e.g. `US`
- At least one of the optional fields is required

**Outputs:**
- `cart` (object): Updated cart, including note, attributes, buyer identity and applied gift cards
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request
- `success` (boolean)

---

#### `storefront_update_cart_note`
Set a note on the cart, such as a gift message or delivery instructions.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `note` (string, required): Note text; an empty string clears the note

**Outputs:**
- `cart` (object): Updated cart, including note, attributes, buyer identity and applied gift cards
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request
- `success` (boolean)

---

#### `storefront_update_cart_attributes`
Replace the cart's custom attributes, such as engraving text.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `attributes` (array, required): `[{key, value}]`; replaces existing attributes, `[]` removes them all

**Outputs:**
- `cart` (object): Updated cart, including note, attributes, buyer identity and applied gift cards
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request
- `success` (boolean)

---

#### `storefront_add_gift_cards`
Apply gift card codes to a cart, keeping any gift cards already applied.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `gift_card_codes` (array, required): Gift card codes

**Outputs:**
- `cart` (object): Updated cart, including note, attributes, buyer identity and applied gift cards
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request
- `success` (boolean)

---

#### `storefront_remove_gift_cards`
Remove applied gift cards from a cart.

**Inputs:**
- `cart_id` (string, required): Cart GraphQL ID
- `applied_gift_card_ids` (array, required): IDs from the cart's `appliedGiftCards`, not the codes

**Outputs:**
- `cart` (object): Updated cart, including note, attributes, buyer identity and applied gift cards
- `warnings` (array, optional): Shopify cart warnings, only present when Shopify changed the request
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

---

#### `storefront_customer_logout`
Sign a customer out by permanently deleting their access token.

**Inputs:**
- `customer_access_token` (string, required): Token from `storefront_customer_login`

**Outputs:**
- `message` (string)
- `success` (boolean)

---

#### `storefront_renew_customer_token`
Extend a customer access token before it expires. An expired token needs a new `storefront_customer_login`.

**Inputs:**
- `customer_access_token` (string, required): Token to renew

**Outputs:**
- `customer_access_token` (string): Renewed token
- `expires_at` (string): New expiry
- `success` (boolean)

---

### Content Actions

#### `storefront_get_shop_policies`
Get the store's privacy, refund, shipping, terms of service and subscription policies. Store details such as name and domain are in the Shopify Admin integration's `get_shop`.

**Inputs:**
None

**Outputs:**
- `policies` (object): `privacy_policy`, `refund_policy`, `shipping_policy`, `terms_of_service`, `subscription_policy`; each has `title`, `handle`, `url`, `body`, or is null when not set
- `success` (boolean)

---

#### `storefront_list_pages`
List the store's content pages, such as About or FAQ.

**Inputs:**
- `first` (integer, optional): Number of pages to return (default: 20)
- `after` (string, optional): Cursor for pagination
- `query` (string, optional): Filter query, e.g. `title:faq`

**Outputs:**
- `pages` (array)
- `count` (integer)
- `has_next_page` (boolean)
- `end_cursor` (string)
- `success` (boolean)

---

#### `storefront_get_page`
Get a content page with its full body.

**Inputs:**
- `handle` (string, optional): Page handle
- `page_id` (string, optional): Page GraphQL ID (used instead of `handle` when both are set)

**Outputs:**
- `page` (object)
- `success` (boolean)

---

#### `storefront_list_articles`
List blog articles across all blogs, newest first.

**Inputs:**
- `first` (integer, optional): Number of articles to return (default: 20)
- `after` (string, optional): Cursor for pagination
- `query` (string, optional): Filter query, e.g. `tag:news` or `blog_title:Journal`

**Outputs:**
- `articles` (array)
- `count` (integer)
- `has_next_page` (boolean)
- `end_cursor` (string)
- `success` (boolean)

---

#### `storefront_get_article`
Get a blog article with its full content.

**Inputs:**
- `article_id` (string, required): Article GraphQL ID from `storefront_list_articles`

**Outputs:**
- `article` (object)
- `success` (boolean)

---

#### `storefront_get_menu`
Get a navigation menu and its items, up to three levels deep.

**Inputs:**
- `handle` (string, required): Menu handle, e.g. `main-menu` or `footer`

**Outputs:**
- `menu` (object)
- `success` (boolean)

---

### Discovery Actions

#### `storefront_get_product_recommendations`
Get up to 10 products recommended for a product.

**Inputs:**
- `product_handle` (string, optional): Product handle
- `product_id` (string, optional): Product GraphQL ID (used instead of `product_handle` when both are set)
- `intent` (string, optional): `RELATED` (default) or `COMPLEMENTARY` (set up in Shopify's Search & Discovery app)

**Outputs:**
- `products` (array)
- `count` (integer)
- `success` (boolean)

---

#### `storefront_predictive_search`
Search-as-you-type suggestions across products, collections, pages and articles, plus suggested search terms. Use `storefront_search_products` for full product search with a total count.

**Inputs:**
- `query` (string, required): Partial search text
- `limit` (integer, optional): Results per type, 1-10 (default: 10)
- `types` (array, optional): Any of `PRODUCT`, `COLLECTION`, `PAGE`, `ARTICLE`, `QUERY`; defaults to all

**Outputs:**
- `queries`, `products`, `collections`, `pages`, `articles` (arrays)
- `success` (boolean)

---

## Requirements

- `autohive-integrations-sdk`
- `aiohttp`

## Usage Examples

### Example 1: Search Products
```python
result = await shopify_storefront.execute_action(
    "storefront_search_products", {"query": "t-shirt", "first": 5}, context
)

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

await shopify_storefront.execute_action(
    "storefront_add_to_cart", {"cart_id": cart_id, "lines": [{"merchandiseId": variant_id, "quantity": 1}]}, context
)
```

### Example 3: Customer Login and Profile
```python
# 1. Login
login_result = await shopify_storefront.execute_action(
    "storefront_customer_login", {"email": "customer@example.com", "password": "securepassword123"}, context
)

token = login_result.data["customer_access_token"]

# 2. Get Profile
profile = await shopify_storefront.execute_action("storefront_get_customer", {"customer_access_token": token}, context)

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
