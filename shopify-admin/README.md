# Shopify Admin Integration for Autohive

Connects Autohive to the Shopify Admin API for comprehensive store management.

## Description

This integration provides access to the Shopify Admin API for managing customers, orders, products, inventory, locations, fulfillments, and draft orders.

**API Implementation:** Shopify GraphQL Admin API for every Admin action. The client-credentials token exchange remains
an OAuth HTTP request, as required by Shopify.

**API Version:** 2026-07

## Setup & Authentication

This integration uses **custom authentication** with credentials from a merchant-owned Shopify app. Autohive does not
own or distribute the Shopify app and does not run a shared Shopify OAuth flow.

Shopify's client credentials grant only works when the app was created by the same organization that owns the store.
It cannot be used to connect an app owned by one organization to unrelated merchants' stores.

### Shopify setup

1. Sign in to the [Shopify Dev Dashboard](https://dev.shopify.com/dashboard) using the organization that owns the store.
2. Create an app and configure the Admin API access scopes listed below.
3. Release the app version and install the app on the store.
4. Open the app's **Settings** page and copy its **Client ID** and **Client secret**.
5. In Autohive, add the Shopify Admin integration and enter:
   - **Shop domain** — the store's permanent domain, such as `your-store.myshopify.com`
   - **Client ID** — the app's Client ID
   - **Client secret** — the app's Client secret

Autohive exchanges these credentials for a short-lived Shopify access token when an action runs. Shopify access tokens
from this flow expire after 24 hours; no access token needs to be copied into Autohive.

**Scopes Required:**
- `read_customers`, `write_customers`
- `read_orders`, `write_orders`
- `read_products`, `write_products`
- `read_inventory`, `write_inventory`
- `read_locations`
- `read_merchant_managed_fulfillment_orders`, `write_merchant_managed_fulfillment_orders`
- `read_draft_orders`, `write_draft_orders`

### Troubleshooting order access

If an order action returns `This action requires merchant approval for read_orders scope`, update the Shopify app rather
than the Autohive integration:

1. Add `read_orders` (and `write_orders` if needed) to a new app version in the Shopify Dev Dashboard.
2. Release that version.
3. Reinstall or update the app on the store and approve the new permissions. Scope changes aren't automatically granted
   to existing installations.
4. Retry the Autohive action. It will request a new access token containing the newly granted scopes.

Order and customer resources are protected customer data. If access remains blocked on a production store, verify the
app's protected customer data configuration in Shopify and request only the customer fields the workflow needs.

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
- `variants` (array, optional): Product variants with `price`, `compare_at_price`, `sku`, `barcode`, `weight`,
  `weight_unit`, and `option_values`. A single variant without `option_values` updates Shopify's automatically created
  standalone variant. Multiple variants must identify every option value, for example
  `{"option_values": [{"option_name": "Size", "name": "Large"}]}`.
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
Submit an asynchronous request to cancel an existing order. The response includes Shopify's cancellation `job_id`,
`job_done`, and a `cancellation_status` of `pending` or `completed`. When Shopify completes the job immediately, the
response also includes the updated order. The action does not poll pending jobs.

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
Create a fulfillment for an order using Shopify's fulfillment-order workflow. The action discovers fulfillment orders
for the supplied `order_id`, selects those assigned to `location_id`, and submits them through the 2026-07 GraphQL
mutation. When `line_items` is omitted, all fulfillable items at that location are fulfilled. Otherwise, provide order
line item IDs and quantities, for example `[{"id": "123", "quantity": 1}]`.

#### `update_fulfillment_tracking`
Update tracking information for a fulfillment.

## Requirements

- `autohive-integrations-sdk`

## Usage Examples

### Example 1: List Products with Pagination (GraphQL)
```python
# First page
result = await shopify_admin.execute_action("list_products", {"limit": 50, "status": "active"}, context)

products = result.data["products"]
has_more = result.data["hasNextPage"]
cursor = result.data["endCursor"]

# Next page
if has_more:
    result = await shopify_admin.execute_action("list_products", {"limit": 50, "after": cursor}, context)
```

### Example 2: Create a Product (GraphQL)
```python
result = await shopify_admin.execute_action(
    "create_product",
    {
        "title": "New Product",
        "body_html": "<p>Product description</p>",
        "vendor": "My Brand",
        "product_type": "Accessories",
        "tags": "new,featured",
        "status": "draft",
        "variants": [{"price": "29.99", "sku": "SKU-001"}],
    },
    context,
)

product_id = result.data["product"]["id"]
```

### Example 3: Update a Product (GraphQL)
```python
result = await shopify_admin.execute_action(
    "update_product",
    {
        "product_id": "12345678",  # or "gid://shopify/Product/12345678"
        "title": "Updated Product Name",
        "status": "active",
    },
    context,
)
```

## Testing

Set the credentials in the repository root `.env` file or export them in your shell:

```bash
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_CLIENT_ID=your-client-id
SHOPIFY_CLIENT_SECRET=your-client-secret
```

Optional resource IDs can be configured with the `SHOPIFY_ADMIN_TEST_*` variables documented in the root
`.env.example`. When an ID isn't supplied, read-only tests discover a resource through the corresponding list action
and skip cleanly if the store has none.

Run the read-only integration tests by default:

```bash
pytest shopify-admin/tests/test_shopify_admin_integration.py -m "integration and not destructive"
```

The destructive suite creates and cleans up customer, product-variant, and draft-order fixtures; it temporarily changes
and restores inventory. It also irreversibly cancels and fulfills disposable orders configured through the
`SHOPIFY_ADMIN_TEST_CANCEL_ORDER_ID`, `SHOPIFY_ADMIN_TEST_FULFILLMENT_ORDER_ID`, and
`SHOPIFY_ADMIN_TEST_FULFILLMENT_LOCATION_ID` variables. Run it deliberately against a test store:

```bash
pytest shopify-admin/tests/test_shopify_admin_integration.py -m "integration and destructive"
```

## Migration Notes (REST to GraphQL)

Shopify's REST Admin API is legacy. Every Admin resource action in this integration now uses the 2026-07 GraphQL Admin
API: customers, orders, products, inventory, locations, shop information, draft orders, and fulfillments.

**Key Changes:**
- Resource IDs can be passed as numeric (`12345`) or GID format (`gid://shopify/Product/12345`)
- Product pagination uses cursor-based pagination; legacy `since_id` filters on other list actions are translated to
  GraphQL search filters
- Filtering uses GraphQL query syntax internally
- Response format is backward-compatible with REST API structure
- Product create and update use the 2026-07 `ProductCreateInput` and `ProductUpdateInput` contracts
- Product variants use `productVariantsBulkCreate` or `productVariantsBulkUpdate`
- Inventory writes use `inventorySetQuantities` with Shopify's required idempotency key
- Fulfillment creation uses fulfillment orders and `fulfillmentCreate`
- `verified_email=false` can't be represented in the GraphQL customer input and is rejected instead of being silently
  ignored; Shopify manages email verification
- `payment_pending` is retained for draft-order compatibility even though Shopify marks that GraphQL argument deprecated;
  newer payment-pending workflows should set payment terms on the draft order

## Resources

- [Create apps using the Shopify Dev Dashboard](https://shopify.dev/docs/apps/build/dev-dashboard/create-apps-using-dev-dashboard)
- [Shopify client credentials grant](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant)
- [Shopify Admin API versioning](https://shopify.dev/docs/api/usage/versioning)
- [Shopify product model](https://shopify.dev/docs/apps/build/product-merchandising/products-and-collections/add-data)
- [Shopify fulfillment-order workflow](https://shopify.dev/docs/apps/build/orders-fulfillment/migrate-to-fulfillment-orders)
