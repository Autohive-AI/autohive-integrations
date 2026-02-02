# Stripe Integration for Autohive

Connects Autohive to the Stripe API to manage customers, invoices, invoice items, subscriptions, products, prices, and payment methods for comprehensive billing and payment processing.

## Description

This integration provides comprehensive access to Stripe's billing functionality, enabling automated invoice creation, customer management, subscription handling, and payment processing. Key features include:

- **Customer Management**: Create, update, list, and delete customers
- **Invoice Management**: Create draft invoices, finalize, send, pay, and void invoices
- **Invoice Items**: Add, update, and remove line items from invoices
- **Subscription Management**: Create, update, list, and cancel subscriptions
- **Product Catalog**: Create and manage products in your catalog
- **Price Management**: Create and manage pricing for products (one-time and recurring)
- **Payment Methods**: List, attach, and detach payment methods for customers


## Setup & Authentication

This integration supports OAuth via Stripe Apps Marketplace for secure authorization.

### OAuth Authentication (Recommended)

1. Install the **Autohive** app from the [Stripe Apps Marketplace](https://marketplace.stripe.com)
2. Authorize Autohive to access your Stripe account
3. The integration will automatically connect via OAuth

### API Key Authentication (Alternative)

1. Log in to your [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Developers** > **API Keys**
3. Copy your **Secret key** (starts with `sk_live_` for production or `sk_test_` for testing)
4. **Important**: Use test keys (`sk_test_`) during development to avoid real charges

**Authentication Fields:**

| Field | Description |
|-------|-------------|
| `api_key` | Your Stripe Secret API Key (starts with `sk_live_` or `sk_test_`) |

## Actions

### Customer Actions

#### `list_customers`
Retrieve a paginated list of customers from Stripe.

**Inputs:**
- `limit` (integer, optional): Number of customers to return (max: 100, default: 10)
- `starting_after` (string, optional): Cursor for pagination
- `email` (string, optional): Filter by customer email address
- `created_gte` (integer, optional): Filter by creation timestamp (Unix)

**Outputs:**
- `customers` (array): List of customer objects
- `has_more` (boolean): Whether there are more customers to fetch
- `result` (boolean): Success status

---

#### `get_customer`
Retrieve details of a specific customer by their ID.

**Inputs:**
- `customer_id` (string, required): The Stripe customer ID (starts with `cus_`)

**Outputs:**
- `customer` (object): Customer details
- `result` (boolean): Success status

---

#### `create_customer`
Create a new customer in Stripe.

**Inputs:**
- `email` (string, optional): Customer's email address
- `name` (string, optional): Customer's full name
- `description` (string, optional): Arbitrary description
- `phone` (string, optional): Customer's phone number
- `address` (object, optional): Customer's address (line1, line2, city, state, postal_code, country)
- `metadata` (object, optional): Key-value pairs for additional data

**Outputs:**
- `customer` (object): Created customer details
- `result` (boolean): Success status

---

#### `update_customer`
Update an existing customer's information.

**Inputs:**
- `customer_id` (string, required): The Stripe customer ID
- `email`, `name`, `description`, `phone`, `address`, `metadata` (optional): Fields to update

**Outputs:**
- `customer` (object): Updated customer details
- `result` (boolean): Success status

---

#### `delete_customer`
Permanently delete a customer from Stripe.

**Inputs:**
- `customer_id` (string, required): The Stripe customer ID to delete

**Outputs:**
- `id` (string): The deleted customer ID
- `deleted` (boolean): Whether the customer was deleted
- `result` (boolean): Success status

---

### Invoice Actions

#### `list_invoices`
Retrieve a paginated list of invoices from Stripe.

**Inputs:**
- `limit` (integer, optional): Number to return (max: 100)
- `customer` (string, optional): Filter by customer ID
- `status` (string, optional): Filter by status: `draft`, `open`, `paid`, `uncollectible`, `void`

**Outputs:**
- `invoices` (array): List of invoice objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_invoice`
Retrieve details of a specific invoice.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID (starts with `in_`)

**Outputs:**
- `invoice` (object): Invoice details
- `result` (boolean): Success status

---

#### `create_invoice`
Create a new draft invoice in Stripe.

**Inputs:**
- `customer` (string, required): The Stripe customer ID to invoice
- `currency` (string, optional): Three-letter ISO currency code (default: `nzd`)
- `description` (string, optional): Invoice memo/description (shown on invoice)
- `auto_advance` (boolean, optional): Whether to auto-finalize (default: `false`)
- `collection_method` (string, optional): `charge_automatically` or `send_invoice`
- `days_until_due` (integer, optional): Days until invoice is due
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `invoice` (object): Created invoice details
- `result` (boolean): Success status

---

#### `update_invoice`
Update a draft invoice's details.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID
- `description`, `auto_advance`, `collection_method`, `days_until_due`, `metadata` (optional)

**Outputs:**
- `invoice` (object): Updated invoice details
- `result` (boolean): Success status

---

#### `delete_invoice`
Permanently delete a draft invoice.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID (must be draft)

**Outputs:**
- `id` (string): The deleted invoice ID
- `deleted` (boolean): Success indicator
- `result` (boolean): Success status

---

#### `finalize_invoice`
Finalize a draft invoice, making it ready for payment.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID
- `auto_advance` (boolean, optional): Whether to auto-advance after finalizing

**Outputs:**
- `invoice` (object): Finalized invoice details
- `result` (boolean): Success status

---

#### `send_invoice`
Send a finalized invoice to the customer via email.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID

**Outputs:**
- `invoice` (object): Sent invoice details
- `result` (boolean): Success status

---

#### `pay_invoice`
Pay an open invoice using the customer's default payment method.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID
- `payment_method` (string, optional): Specific payment method ID

**Outputs:**
- `invoice` (object): Paid invoice details
- `result` (boolean): Success status

---

#### `void_invoice`
Void an open invoice, marking it as uncollectible.

**Inputs:**
- `invoice_id` (string, required): The Stripe invoice ID

**Outputs:**
- `invoice` (object): Voided invoice details
- `result` (boolean): Success status

---

### Invoice Item Actions

#### `list_invoice_items`
Retrieve a paginated list of invoice items.

**Inputs:**
- `limit` (integer, optional): Number to return (max: 100)
- `customer` (string, optional): Filter by customer ID
- `invoice` (string, optional): Filter by invoice ID
- `pending` (boolean, optional): Filter for pending items

**Outputs:**
- `invoice_items` (array): List of invoice item objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_invoice_item`
Retrieve details of a specific invoice item.

**Inputs:**
- `invoice_item_id` (string, required): The Stripe invoice item ID (starts with `ii_`)

**Outputs:**
- `invoice_item` (object): Invoice item details
- `result` (boolean): Success status

---

#### `create_invoice_item`
Create a new invoice item and optionally attach to a draft invoice.

**Inputs:**
- `customer` (string, required): The Stripe customer ID
- `invoice` (string, optional): Invoice ID to attach to (must be draft)
- `amount` (integer, optional): Amount in cents
- `currency` (string, optional): Currency code (default: `nzd`)
- `description` (string, optional): Line item description
- `quantity` (integer, optional): Quantity of units
- `unit_amount` (integer, optional): Unit price in cents
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `invoice_item` (object): Created invoice item details
- `result` (boolean): Success status

---

#### `update_invoice_item`
Update an existing invoice item.

**Inputs:**
- `invoice_item_id` (string, required): The Stripe invoice item ID
- `amount`, `description`, `quantity`, `unit_amount`, `metadata` (optional)

**Outputs:**
- `invoice_item` (object): Updated invoice item details
- `result` (boolean): Success status

---

#### `delete_invoice_item`
Delete an invoice item.

**Inputs:**
- `invoice_item_id` (string, required): The Stripe invoice item ID

**Outputs:**
- `id` (string): The deleted invoice item ID
- `deleted` (boolean): Success indicator
- `result` (boolean): Success status

---

### Subscription Actions

#### `list_subscriptions`
Retrieve a paginated list of subscriptions from Stripe.

**Inputs:**
- `limit` (integer, optional): Number to return (max: 100, default: 10)
- `customer` (string, optional): Filter by customer ID
- `status` (string, optional): Filter by status: `active`, `past_due`, `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `trialing`, `paused`, `all`
- `price` (string, optional): Filter by price ID
- `starting_after` (string, optional): Cursor for pagination

**Outputs:**
- `subscriptions` (array): List of subscription objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_subscription`
Retrieve details of a specific subscription.

**Inputs:**
- `subscription_id` (string, required): The Stripe subscription ID (starts with `sub_`)

**Outputs:**
- `subscription` (object): Subscription details
- `result` (boolean): Success status

---

#### `create_subscription`
Create a new subscription for a customer.

**Inputs:**
- `customer` (string, required): The Stripe customer ID
- `items` (array, required): Subscription items with price IDs and quantities
- `payment_behavior` (string, optional): `default_incomplete`, `error_if_incomplete`, `allow_incomplete`, `pending_if_incomplete`
- `trial_period_days` (integer, optional): Number of trial days
- `cancel_at_period_end` (boolean, optional): Cancel at end of billing period
- `billing_cycle_anchor` (integer, optional): Unix timestamp for billing cycle start
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `subscription` (object): Created subscription details
- `result` (boolean): Success status

---

#### `update_subscription`
Update an existing subscription.

**Inputs:**
- `subscription_id` (string, required): The Stripe subscription ID
- `items` (array, optional): Updated subscription items
- `cancel_at_period_end` (boolean, optional): Cancel at end of period
- `trial_end` (string, optional): Unix timestamp or `now` to end trial
- `payment_behavior` (string, optional): Payment behavior for updates
- `proration_behavior` (string, optional): `create_prorations`, `none`, `always_invoice`
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `subscription` (object): Updated subscription details
- `result` (boolean): Success status

---

#### `cancel_subscription`
Cancel a subscription immediately or at period end.

**Inputs:**
- `subscription_id` (string, required): The Stripe subscription ID
- `cancel_at_period_end` (boolean, optional): If true, cancel at end of period instead of immediately
- `invoice_now` (boolean, optional): Generate final invoice
- `prorate` (boolean, optional): Prorate final invoice

**Outputs:**
- `subscription` (object): Canceled subscription details
- `result` (boolean): Success status

---

### Product Actions

#### `list_products`
Retrieve a paginated list of products from Stripe.

**Inputs:**
- `limit` (integer, optional): Number to return (max: 100, default: 10)
- `active` (boolean, optional): Filter by active status
- `starting_after` (string, optional): Cursor for pagination

**Outputs:**
- `products` (array): List of product objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_product`
Retrieve details of a specific product.

**Inputs:**
- `product_id` (string, required): The Stripe product ID (starts with `prod_`)

**Outputs:**
- `product` (object): Product details
- `result` (boolean): Success status

---

#### `create_product`
Create a new product in Stripe.

**Inputs:**
- `name` (string, required): Product name
- `description` (string, optional): Product description
- `active` (boolean, optional): Whether product is active (default: true)
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `product` (object): Created product details
- `result` (boolean): Success status

---

#### `update_product`
Update an existing product.

**Inputs:**
- `product_id` (string, required): The Stripe product ID
- `name` (string, optional): Updated product name
- `description` (string, optional): Updated description
- `active` (boolean, optional): Active status
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `product` (object): Updated product details
- `result` (boolean): Success status

---

### Price Actions

#### `list_prices`
Retrieve a paginated list of prices from Stripe.

**Inputs:**
- `limit` (integer, optional): Number to return (max: 100, default: 10)
- `product` (string, optional): Filter by product ID
- `active` (boolean, optional): Filter by active status
- `type` (string, optional): Filter by type: `one_time` or `recurring`
- `starting_after` (string, optional): Cursor for pagination

**Outputs:**
- `prices` (array): List of price objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_price`
Retrieve details of a specific price.

**Inputs:**
- `price_id` (string, required): The Stripe price ID (starts with `price_`)

**Outputs:**
- `price` (object): Price details
- `result` (boolean): Success status

---

#### `create_price`
Create a new price for a product.

**Inputs:**
- `product` (string, required): The Stripe product ID
- `currency` (string, required): Three-letter ISO currency code (e.g., `usd`, `nzd`)
- `unit_amount` (integer, required): Amount in cents
- `recurring` (object, optional): Recurring pricing config with `interval` (`day`, `week`, `month`, `year`) and `interval_count`
- `active` (boolean, optional): Whether price is active
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `price` (object): Created price details
- `result` (boolean): Success status

---

#### `update_price`
Update an existing price (limited fields).

**Inputs:**
- `price_id` (string, required): The Stripe price ID
- `active` (boolean, optional): Active status
- `metadata` (object, optional): Key-value pairs

**Outputs:**
- `price` (object): Updated price details
- `result` (boolean): Success status

---

### Payment Method Actions

#### `list_payment_methods`
List payment methods for a customer.

**Inputs:**
- `customer` (string, required): The Stripe customer ID
- `type` (string, optional): Payment method type: `card`, `us_bank_account`, `sepa_debit`, etc. (default: `card`)
- `limit` (integer, optional): Number to return (max: 100, default: 10)
- `starting_after` (string, optional): Cursor for pagination

**Outputs:**
- `payment_methods` (array): List of payment method objects
- `has_more` (boolean): Pagination indicator
- `result` (boolean): Success status

---

#### `get_payment_method`
Retrieve details of a specific payment method.

**Inputs:**
- `payment_method_id` (string, required): The Stripe payment method ID (starts with `pm_`)

**Outputs:**
- `payment_method` (object): Payment method details
- `result` (boolean): Success status

---

#### `attach_payment_method`
Attach a payment method to a customer.

**Inputs:**
- `payment_method_id` (string, required): The Stripe payment method ID
- `customer` (string, required): The Stripe customer ID to attach to

**Outputs:**
- `payment_method` (object): Attached payment method details
- `result` (boolean): Success status

---

#### `detach_payment_method`
Detach a payment method from a customer.

**Inputs:**
- `payment_method_id` (string, required): The Stripe payment method ID

**Outputs:**
- `payment_method` (object): Detached payment method details
- `result` (boolean): Success status

---

## Requirements

- `autohive-integrations-sdk` (Autohive Integration SDK)

## Usage Examples

### Example 1: Create a RUC Invoice

```python
# 1. Create the invoice
invoice = await stripe.execute_action("create_invoice", {
    "customer": "cus_xxxxx",
    "currency": "nzd",
    "description": "RUC Purchase - GTR680 (John's BMW)\n5 units (5,000km)",
    "auto_advance": False,
    "collection_method": "send_invoice",
    "days_until_due": 30
}, context)

invoice_id = invoice.data["invoice"]["id"]

# 2. Add RUC line item ($66.09 x 5 units)
await stripe.execute_action("create_invoice_item", {
    "customer": "cus_xxxxx",
    "invoice": invoice_id,
    "unit_amount": 6609,  # cents
    "currency": "nzd",
    "quantity": 5,
    "description": "RUC - 5 units (5,000km)"
}, context)

# 3. Add NZTA Fee
await stripe.execute_action("create_invoice_item", {
    "customer": "cus_xxxxx",
    "invoice": invoice_id,
    "unit_amount": 1082,  # $10.82 in cents
    "currency": "nzd",
    "quantity": 1,
    "description": "NZTA Administration Fee"
}, context)

# 4. Add BONNET Processing Fee
await stripe.execute_action("create_invoice_item", {
    "customer": "cus_xxxxx",
    "invoice": invoice_id,
    "unit_amount": 600,  # $6.00 in cents
    "currency": "nzd",
    "quantity": 1,
    "description": "BONNET Processing Fee"
}, context)

# Invoice is now ready as draft for review
```

### Example 2: List Draft Invoices for a Customer

```python
result = await stripe.execute_action("list_invoices", {
    "customer": "cus_xxxxx",
    "status": "draft",
    "limit": 10
}, context)

for invoice in result.data["invoices"]:
    print(f"Invoice {invoice['id']}: ${invoice['total']/100:.2f}")
```

## Testing

To run the tests:

1. Navigate to the integration's directory:
   ```bash
   cd stripe
   ```

2. Set your test API key:
   ```bash
   export STRIPE_TEST_API_KEY=sk_test_your_key_here
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the tests:
   ```bash
   python tests/test_stripe.py
   ```

**Note**: Always use test API keys (`sk_test_`) when running tests to avoid creating real charges.

## API Reference

- [Stripe API Documentation](https://docs.stripe.com/api)
- [Customers API](https://docs.stripe.com/api/customers)
- [Invoices API](https://docs.stripe.com/api/invoices)
- [Invoice Items API](https://docs.stripe.com/api/invoiceitems)
- [Subscriptions API](https://docs.stripe.com/api/subscriptions)
- [Products API](https://docs.stripe.com/api/products)
- [Prices API](https://docs.stripe.com/api/prices)
- [Payment Methods API](https://docs.stripe.com/api/payment_methods)
- [Stripe Apps Marketplace](https://marketplace.stripe.com)
