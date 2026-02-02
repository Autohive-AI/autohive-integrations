# Shopify Admin Integration for Autohive

Connects Autohive to the Shopify Admin API for comprehensive store management.

## Description

This integration provides access to the Shopify Admin API for managing customers, orders, products, inventory, locations, fulfillments, and draft orders.

**API Implementation:**
- **Products**: GraphQL Admin API (migrated from REST - compliant with 2024-04 deprecation)
- **Other resources**: REST Admin API

**API Version:** 2024-10

## Setup & Authentication

This integration uses **Platform Authentication** with Shopify (Admin API).

**Scopes Required:**
- `read_customers`, `write_customers`
- `read_orders`, `write_orders`
- `read_products`, `write_products`
- `read_inventory`, `write_inventory`
- `read_locations`
- `read_fulfillments`, `write_fulfillments`
- `read_draft_orders`, `write_draft_orders`

## Actions

### Product Actions (GraphQL)

#### `list_products`
List products with optional filtering using GraphQL API.

**Inputs:**
- `limit` (integer, optional): Maximum products to return (max 250, default: 50)
- `after` (string, optional): Cursor for pagination (from `endCursor`)
- `title` (string, optional): Filter by title (partial match)
- `vendor` (string, optional): Filter by vendor
- `product_type` (string, optional): Filter by product type
- `status` (string, optional): Filter by status (`active`, `archived`, `draft`)
- `created_at_min` (string, optional): Created after (ISO 8601)
- `created_at_max` (string, optional): Created before (ISO 8601)

**Outputs:**
- `products` (array): List of products with variants, options, and images
- `count` (integer): Number of products returned
- `hasNextPage` (boolean): Whether more results exist
- `endCursor` (string): Cursor for next page
- `success` (boolean)

---

#### `get_product`
Get a single product by ID using GraphQL API.

**Inputs:**
- `product_id` (string, required): Product ID (numeric or GID format)

**Outputs:**
- `product` (object): Product details with variants, options, and images
- `success` (boolean)

---

#### `create_product`
Create a new product using GraphQL API.

**Inputs:**
- `title` (string, required): Product title
- `body_html` (string, optional): Description HTML
- `vendor` (string, optional): Vendor name
- `product_type` (string, optional): Product type
- `tags` (string, optional): Comma-separated tags
- `status` (string, optional): Status (`active`, `archived`, `draft`)
- `variants` (array, optional): Product variants with `price`, `sku`, `barcode`, `weight`
- `options` (array, optional): Product options (e.g., Size, Color)

**Outputs:**
- `product` (object): Created product details
- `success` (boolean)

---

#### `update_product`
Update an existing product using GraphQL API.

**Inputs:**
- `product_id` (string, required): Product ID (numeric or GID format)
- `title` (string, optional): Title
- `body_html` (string, optional): Description HTML
- `vendor` (string, optional): Vendor
- `product_type` (string, optional): Product type
- `tags` (string, optional): Comma-separated tags
- `status` (string, optional): Status

**Note:** Variant updates require separate API calls.

**Outputs:**
- `product` (object): Updated product details
- `success` (boolean)

---

### Customer Actions

#### `list_customers`
List customers with optional filtering and pagination.

#### `get_customer`
Get a single customer by ID.

#### `search_customers`
Search customers by query string.

#### `create_customer`
Create a new customer.

#### `update_customer`
Update an existing customer.

---

### Order Actions

#### `list_orders`
List orders with optional filtering.

#### `get_order`
Get a single order by ID.

#### `create_order`
Create a new order.

#### `cancel_order`
Cancel an existing order.

---

### Inventory & Location Actions

#### `get_inventory_levels`
Get inventory levels by location or item IDs.

#### `set_inventory_level`
Set inventory level for an item at a location.

#### `list_locations`
List all store locations.

#### `get_location`
Get a single location by ID.

---

### Shop Actions

#### `get_shop`
Get store information.

---

### Draft Order Actions

#### `list_draft_orders`
List draft orders.

#### `create_draft_order`
Create a new draft order.

#### `complete_draft_order`
Complete a draft order, converting to a real order.

#### `delete_draft_order`
Delete a draft order.

---

### Fulfillment Actions

#### `list_fulfillments`
List fulfillments for an order.

#### `create_fulfillment`
Create a fulfillment for an order.

#### `update_fulfillment_tracking`
Update tracking information for a fulfillment.

## Requirements

- `autohive-integrations-sdk`

## Usage Examples

### Example 1: List Products with Pagination (GraphQL)
```python
# First page
result = await shopify_admin.execute_action("list_products", {
    "limit": 50,
    "status": "active"
}, context)

products = result.data["products"]
has_more = result.data["hasNextPage"]
cursor = result.data["endCursor"]

# Next page
if has_more:
    result = await shopify_admin.execute_action("list_products", {
        "limit": 50,
        "after": cursor
    }, context)
```

### Example 2: Create a Product (GraphQL)
```python
result = await shopify_admin.execute_action("create_product", {
    "title": "New Product",
    "body_html": "<p>Product description</p>",
    "vendor": "My Brand",
    "product_type": "Accessories",
    "tags": "new,featured",
    "status": "draft",
    "variants": [
        {"price": "29.99", "sku": "SKU-001"}
    ]
}, context)

product_id = result.data["product"]["id"]
```

### Example 3: Update a Product (GraphQL)
```python
result = await shopify_admin.execute_action("update_product", {
    "product_id": "12345678",  # or "gid://shopify/Product/12345678"
    "title": "Updated Product Name",
    "status": "active"
}, context)
```

## Testing

To run the tests:

1. Set environment variables:
   ```bash
   export SHOPIFY_ADMIN_TOKEN="your-access-token"
   export SHOPIFY_STORE_URL="your-store.myshopify.com"
   ```

2. Navigate to the tests directory:
   ```bash
   cd shopify-admin/tests
   ```

3. Run tests:
   ```bash
   python test_shopify_admin.py safe     # Read-only tests
   python test_shopify_admin.py get      # Get-by-ID tests
   python test_shopify_admin.py write    # Create tests
   python test_shopify_admin.py update   # Update tests
   python test_shopify_admin.py all      # All tests
   ```

## Migration Notes (REST to GraphQL)

As of April 2024, Shopify deprecated the REST Admin API `/products` and `/variants` endpoints. This integration has been migrated to use the GraphQL Admin API for all product operations.

**Key Changes:**
- Product IDs can be passed as numeric (`12345`) or GID format (`gid://shopify/Product/12345`)
- Pagination uses cursor-based approach (`after` parameter) instead of `since_id`
- Filtering uses GraphQL query syntax internally
- Response format is backward-compatible with REST API structure
