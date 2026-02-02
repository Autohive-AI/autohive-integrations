from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler,
    ActionResult
)
from typing import Dict, Any


# Load integration from config.json
stripe = Integration.load()

# Base URL for Stripe API
STRIPE_API_BASE_URL = "https://api.stripe.com"
API_VERSION = "v1"


# ---- Helper Functions ----

def get_common_headers() -> Dict[str, str]:
    """
    Return common headers for Stripe API requests.
    Auth headers are automatically added by the SDK when using platform auth.
    """
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Stripe-Version": "2025-12-15.preview"
    }


def build_form_data(data: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """
    Convert nested dict to Stripe's form-encoded format.
    Stripe requires nested objects as key[subkey]=value format.

    Args:
        data: Dictionary to convert
        prefix: Prefix for nested keys

    Returns:
        Flattened dictionary for form encoding
    """
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}[{key}]" if prefix else key

        if isinstance(value, dict):
            result.update(build_form_data(value, full_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    result.update(build_form_data(item, f"{full_key}[{i}]"))
                else:
                    result[f"{full_key}[{i}]"] = str(item)
        elif value is not None:
            if isinstance(value, bool):
                result[full_key] = "true" if value else "false"
            else:
                result[full_key] = str(value)

    return result


def build_list_params(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build query parameters for list endpoints."""
    params = {}

    if 'limit' in inputs and inputs['limit']:
        params['limit'] = min(inputs['limit'], 100)
    if 'starting_after' in inputs and inputs['starting_after']:
        params['starting_after'] = inputs['starting_after']
    if 'ending_before' in inputs and inputs['ending_before']:
        params['ending_before'] = inputs['ending_before']

    return params


# ---- Customer Action Handlers ----

@stripe.action("list_customers")
class ListCustomersAction(ActionHandler):
    """Retrieve a paginated list of customers from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'email' in inputs and inputs['email']:
                params['email'] = inputs['email']
            if 'created_gte' in inputs and inputs['created_gte']:
                params['created[gte]'] = inputs['created_gte']
            if 'created_lte' in inputs and inputs['created_lte']:
                params['created[lte]'] = inputs['created_lte']

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/customers",
                method="GET",
                headers=headers,
                params=params
            )

            customers = response.get('data', [])

            return ActionResult(
                data={
                    "customers": customers,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customers": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_customer")
class GetCustomerAction(ActionHandler):
    """Retrieve details of a specific customer by their ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs['customer_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "customer": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_customer")
class CreateCustomerAction(ActionHandler):
    """Create a new customer in Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {}

            # Add optional fields
            if 'email' in inputs and inputs['email']:
                body['email'] = inputs['email']
            if 'name' in inputs and inputs['name']:
                body['name'] = inputs['name']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'phone' in inputs and inputs['phone']:
                body['phone'] = inputs['phone']
            if 'address' in inputs and inputs['address']:
                body['address'] = inputs['address']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/customers",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "customer": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_customer")
class UpdateCustomerAction(ActionHandler):
    """Update an existing customer's information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs['customer_id']
            body = {}

            # Add only provided fields
            if 'email' in inputs and inputs['email']:
                body['email'] = inputs['email']
            if 'name' in inputs and inputs['name']:
                body['name'] = inputs['name']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'phone' in inputs and inputs['phone']:
                body['phone'] = inputs['phone']
            if 'address' in inputs and inputs['address']:
                body['address'] = inputs['address']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "customer": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "customer": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("delete_customer")
class DeleteCustomerAction(ActionHandler):
    """Permanently delete a customer from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs['customer_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/customers/{customer_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "id": response.get('id', customer_id),
                    "deleted": response.get('deleted', True),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get('customer_id', ''),
                    "deleted": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Invoice Action Handlers ----

@stripe.action("list_invoices")
class ListInvoicesAction(ActionHandler):
    """Retrieve a paginated list of invoices from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'customer' in inputs and inputs['customer']:
                params['customer'] = inputs['customer']
            if 'status' in inputs and inputs['status']:
                params['status'] = inputs['status']
            if 'created_gte' in inputs and inputs['created_gte']:
                params['created[gte]'] = inputs['created_gte']
            if 'created_lte' in inputs and inputs['created_lte']:
                params['created[lte]'] = inputs['created_lte']

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices",
                method="GET",
                headers=headers,
                params=params
            )

            invoices = response.get('data', [])

            return ActionResult(
                data={
                    "invoices": invoices,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoices": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_invoice")
class GetInvoiceAction(ActionHandler):
    """Retrieve details of a specific invoice by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_invoice")
class CreateInvoiceAction(ActionHandler):
    """Create a new draft invoice in Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "customer": inputs['customer']
            }

            # Add optional fields
            if 'currency' in inputs and inputs['currency']:
                body['currency'] = inputs['currency']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'auto_advance' in inputs:
                body['auto_advance'] = inputs['auto_advance']
            if 'collection_method' in inputs and inputs['collection_method']:
                body['collection_method'] = inputs['collection_method']
            if 'days_until_due' in inputs and inputs['days_until_due']:
                body['days_until_due'] = inputs['days_until_due']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_invoice")
class UpdateInvoiceAction(ActionHandler):
    """Update a draft invoice's details."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            body = {}

            # Add only provided fields
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'auto_advance' in inputs:
                body['auto_advance'] = inputs['auto_advance']
            if 'collection_method' in inputs and inputs['collection_method']:
                body['collection_method'] = inputs['collection_method']
            if 'days_until_due' in inputs and inputs['days_until_due']:
                body['days_until_due'] = inputs['days_until_due']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("delete_invoice")
class DeleteInvoiceAction(ActionHandler):
    """Permanently delete a draft invoice."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "id": response.get('id', invoice_id),
                    "deleted": response.get('deleted', True),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get('invoice_id', ''),
                    "deleted": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("finalize_invoice")
class FinalizeInvoiceAction(ActionHandler):
    """Finalize a draft invoice, making it ready for payment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            body = {}

            if 'auto_advance' in inputs:
                body['auto_advance'] = inputs['auto_advance']

            headers = get_common_headers()
            form_data = build_form_data(body) if body else {}

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}/finalize",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("send_invoice")
class SendInvoiceAction(ActionHandler):
    """Send a finalized invoice to the customer via email."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}/send",
                method="POST",
                headers=headers
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("pay_invoice")
class PayInvoiceAction(ActionHandler):
    """Pay an open invoice using the customer's default payment method."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            body = {}

            if 'payment_method' in inputs and inputs['payment_method']:
                body['payment_method'] = inputs['payment_method']

            headers = get_common_headers()
            form_data = build_form_data(body) if body else {}

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}/pay",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("void_invoice")
class VoidInvoiceAction(ActionHandler):
    """Void an open invoice, marking it as uncollectible."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_id = inputs['invoice_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoices/{invoice_id}/void",
                method="POST",
                headers=headers
            )

            return ActionResult(
                data={
                    "invoice": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Invoice Item Action Handlers ----

@stripe.action("list_invoice_items")
class ListInvoiceItemsAction(ActionHandler):
    """Retrieve a paginated list of invoice items."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'customer' in inputs and inputs['customer']:
                params['customer'] = inputs['customer']
            if 'invoice' in inputs and inputs['invoice']:
                params['invoice'] = inputs['invoice']
            if 'pending' in inputs:
                params['pending'] = 'true' if inputs['pending'] else 'false'

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoiceitems",
                method="GET",
                headers=headers,
                params=params
            )

            invoice_items = response.get('data', [])

            return ActionResult(
                data={
                    "invoice_items": invoice_items,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice_items": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_invoice_item")
class GetInvoiceItemAction(ActionHandler):
    """Retrieve details of a specific invoice item by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_item_id = inputs['invoice_item_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoiceitems/{invoice_item_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "invoice_item": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice_item": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_invoice_item")
class CreateInvoiceItemAction(ActionHandler):
    """Create a new invoice item and optionally attach to a draft invoice."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "customer": inputs['customer']
            }

            # Add optional fields
            if 'invoice' in inputs and inputs['invoice']:
                body['invoice'] = inputs['invoice']
            if 'amount' in inputs and inputs['amount'] is not None:
                body['amount'] = inputs['amount']
            if 'currency' in inputs and inputs['currency']:
                body['currency'] = inputs['currency']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'quantity' in inputs and inputs['quantity'] is not None:
                body['quantity'] = inputs['quantity']
            if 'unit_amount' in inputs and inputs['unit_amount'] is not None:
                body['unit_amount_decimal'] = inputs['unit_amount']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoiceitems",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice_item": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice_item": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_invoice_item")
class UpdateInvoiceItemAction(ActionHandler):
    """Update an existing invoice item."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_item_id = inputs['invoice_item_id']
            body = {}

            # Add only provided fields
            if 'amount' in inputs and inputs['amount'] is not None:
                body['amount'] = inputs['amount']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'quantity' in inputs and inputs['quantity'] is not None:
                body['quantity'] = inputs['quantity']
            if 'unit_amount' in inputs and inputs['unit_amount'] is not None:
                body['unit_amount_decimal'] = inputs['unit_amount']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoiceitems/{invoice_item_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "invoice_item": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "invoice_item": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("delete_invoice_item")
class DeleteInvoiceItemAction(ActionHandler):
    """Delete an invoice item that hasn't been attached to an invoice."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            invoice_item_id = inputs['invoice_item_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/invoiceitems/{invoice_item_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "id": response.get('id', invoice_item_id),
                    "deleted": response.get('deleted', True),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get('invoice_item_id', ''),
                    "deleted": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Product Action Handlers ----

@stripe.action("list_products")
class ListProductsAction(ActionHandler):
    """Retrieve a paginated list of products from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'active' in inputs and inputs['active'] is not None:
                params['active'] = 'true' if inputs['active'] else 'false'
            if 'type' in inputs and inputs['type']:
                params['type'] = inputs['type']
            if 'created_gte' in inputs and inputs['created_gte']:
                params['created[gte]'] = inputs['created_gte']
            if 'created_lte' in inputs and inputs['created_lte']:
                params['created[lte]'] = inputs['created_lte']

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/products",
                method="GET",
                headers=headers,
                params=params
            )

            products = response.get('data', [])

            return ActionResult(
                data={
                    "products": products,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "products": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_product")
class GetProductAction(ActionHandler):
    """Retrieve details of a specific product by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            product_id = inputs['product_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/products/{product_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "product": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "product": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_product")
class CreateProductAction(ActionHandler):
    """Create a new product in Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "name": inputs['name']
            }

            # Add optional fields
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'active' in inputs and inputs['active'] is not None:
                body['active'] = inputs['active']
            if 'default_price_data' in inputs and inputs['default_price_data']:
                body['default_price_data'] = inputs['default_price_data']
            if 'images' in inputs and inputs['images']:
                body['images'] = inputs['images']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']
            if 'tax_code' in inputs and inputs['tax_code']:
                body['tax_code'] = inputs['tax_code']
            if 'unit_label' in inputs and inputs['unit_label']:
                body['unit_label'] = inputs['unit_label']
            if 'url' in inputs and inputs['url']:
                body['url'] = inputs['url']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/products",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "product": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "product": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_product")
class UpdateProductAction(ActionHandler):
    """Update an existing product's information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            product_id = inputs['product_id']
            body = {}

            # Add only provided fields
            if 'name' in inputs and inputs['name']:
                body['name'] = inputs['name']
            if 'description' in inputs and inputs['description']:
                body['description'] = inputs['description']
            if 'active' in inputs and inputs['active'] is not None:
                body['active'] = inputs['active']
            if 'default_price' in inputs and inputs['default_price']:
                body['default_price'] = inputs['default_price']
            if 'images' in inputs and inputs['images']:
                body['images'] = inputs['images']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']
            if 'tax_code' in inputs and inputs['tax_code']:
                body['tax_code'] = inputs['tax_code']
            if 'unit_label' in inputs and inputs['unit_label']:
                body['unit_label'] = inputs['unit_label']
            if 'url' in inputs and inputs['url']:
                body['url'] = inputs['url']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/products/{product_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "product": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "product": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Price Action Handlers ----

@stripe.action("list_prices")
class ListPricesAction(ActionHandler):
    """Retrieve a paginated list of prices from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'active' in inputs and inputs['active'] is not None:
                params['active'] = 'true' if inputs['active'] else 'false'
            if 'product' in inputs and inputs['product']:
                params['product'] = inputs['product']
            if 'type' in inputs and inputs['type']:
                params['type'] = inputs['type']
            if 'currency' in inputs and inputs['currency']:
                params['currency'] = inputs['currency']
            if 'created_gte' in inputs and inputs['created_gte']:
                params['created[gte]'] = inputs['created_gte']
            if 'created_lte' in inputs and inputs['created_lte']:
                params['created[lte]'] = inputs['created_lte']

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/prices",
                method="GET",
                headers=headers,
                params=params
            )

            prices = response.get('data', [])

            return ActionResult(
                data={
                    "prices": prices,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "prices": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_price")
class GetPriceAction(ActionHandler):
    """Retrieve details of a specific price by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            price_id = inputs['price_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/prices/{price_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "price": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "price": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_price")
class CreatePriceAction(ActionHandler):
    """Create a new price for a product in Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "currency": inputs.get('currency', 'usd'),
                "product": inputs['product']
            }

            # Add unit_amount or custom_unit_amount
            if 'unit_amount' in inputs and inputs['unit_amount'] is not None:
                body['unit_amount'] = inputs['unit_amount']
            elif 'unit_amount_decimal' in inputs and inputs['unit_amount_decimal']:
                body['unit_amount_decimal'] = inputs['unit_amount_decimal']

            # Add optional fields
            if 'active' in inputs and inputs['active'] is not None:
                body['active'] = inputs['active']
            if 'nickname' in inputs and inputs['nickname']:
                body['nickname'] = inputs['nickname']
            if 'recurring' in inputs and inputs['recurring']:
                body['recurring'] = inputs['recurring']
            if 'billing_scheme' in inputs and inputs['billing_scheme']:
                body['billing_scheme'] = inputs['billing_scheme']
            if 'tiers' in inputs and inputs['tiers']:
                body['tiers'] = inputs['tiers']
            if 'tiers_mode' in inputs and inputs['tiers_mode']:
                body['tiers_mode'] = inputs['tiers_mode']
            if 'tax_behavior' in inputs and inputs['tax_behavior']:
                body['tax_behavior'] = inputs['tax_behavior']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/prices",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "price": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "price": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_price")
class UpdatePriceAction(ActionHandler):
    """Update an existing price (limited fields can be updated)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            price_id = inputs['price_id']
            body = {}

            # Only certain fields can be updated on a price
            if 'active' in inputs and inputs['active'] is not None:
                body['active'] = inputs['active']
            if 'nickname' in inputs and inputs['nickname']:
                body['nickname'] = inputs['nickname']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']
            if 'tax_behavior' in inputs and inputs['tax_behavior']:
                body['tax_behavior'] = inputs['tax_behavior']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/prices/{price_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "price": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "price": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Subscription Action Handlers ----

@stripe.action("list_subscriptions")
class ListSubscriptionsAction(ActionHandler):
    """Retrieve a paginated list of subscriptions from Stripe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Add optional filters
            if 'customer' in inputs and inputs['customer']:
                params['customer'] = inputs['customer']
            if 'price' in inputs and inputs['price']:
                params['price'] = inputs['price']
            if 'status' in inputs and inputs['status']:
                params['status'] = inputs['status']
            if 'created_gte' in inputs and inputs['created_gte']:
                params['created[gte]'] = inputs['created_gte']
            if 'created_lte' in inputs and inputs['created_lte']:
                params['created[lte]'] = inputs['created_lte']
            if 'current_period_start_gte' in inputs and inputs['current_period_start_gte']:
                params['current_period_start[gte]'] = inputs['current_period_start_gte']
            if 'current_period_start_lte' in inputs and inputs['current_period_start_lte']:
                params['current_period_start[lte]'] = inputs['current_period_start_lte']

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions",
                method="GET",
                headers=headers,
                params=params
            )

            subscriptions = response.get('data', [])

            return ActionResult(
                data={
                    "subscriptions": subscriptions,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "subscriptions": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_subscription")
class GetSubscriptionAction(ActionHandler):
    """Retrieve details of a specific subscription by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            subscription_id = inputs['subscription_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions/{subscription_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "subscription": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "subscription": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("create_subscription")
class CreateSubscriptionAction(ActionHandler):
    """Create a new subscription for a customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "customer": inputs['customer']
            }

            # Add items (required for most subscriptions)
            if 'items' in inputs and inputs['items']:
                body['items'] = inputs['items']

            # Add optional fields
            if 'default_payment_method' in inputs and inputs['default_payment_method']:
                body['default_payment_method'] = inputs['default_payment_method']
            if 'payment_behavior' in inputs and inputs['payment_behavior']:
                body['payment_behavior'] = inputs['payment_behavior']
            if 'billing_cycle_anchor' in inputs and inputs['billing_cycle_anchor']:
                body['billing_cycle_anchor'] = inputs['billing_cycle_anchor']
            if 'cancel_at_period_end' in inputs and inputs['cancel_at_period_end'] is not None:
                body['cancel_at_period_end'] = inputs['cancel_at_period_end']
            if 'cancel_at' in inputs and inputs['cancel_at']:
                body['cancel_at'] = inputs['cancel_at']
            if 'collection_method' in inputs and inputs['collection_method']:
                body['collection_method'] = inputs['collection_method']
            if 'days_until_due' in inputs and inputs['days_until_due']:
                body['days_until_due'] = inputs['days_until_due']
            if 'trial_period_days' in inputs and inputs['trial_period_days']:
                body['trial_period_days'] = inputs['trial_period_days']
            if 'trial_end' in inputs and inputs['trial_end']:
                body['trial_end'] = inputs['trial_end']
            if 'proration_behavior' in inputs and inputs['proration_behavior']:
                body['proration_behavior'] = inputs['proration_behavior']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "subscription": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "subscription": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("update_subscription")
class UpdateSubscriptionAction(ActionHandler):
    """Update an existing subscription."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            subscription_id = inputs['subscription_id']
            body = {}

            # Add only provided fields
            if 'items' in inputs and inputs['items']:
                body['items'] = inputs['items']
            if 'default_payment_method' in inputs and inputs['default_payment_method']:
                body['default_payment_method'] = inputs['default_payment_method']
            if 'payment_behavior' in inputs and inputs['payment_behavior']:
                body['payment_behavior'] = inputs['payment_behavior']
            if 'cancel_at_period_end' in inputs and inputs['cancel_at_period_end'] is not None:
                body['cancel_at_period_end'] = inputs['cancel_at_period_end']
            if 'cancel_at' in inputs and inputs['cancel_at']:
                body['cancel_at'] = inputs['cancel_at']
            if 'collection_method' in inputs and inputs['collection_method']:
                body['collection_method'] = inputs['collection_method']
            if 'days_until_due' in inputs and inputs['days_until_due']:
                body['days_until_due'] = inputs['days_until_due']
            if 'trial_end' in inputs and inputs['trial_end']:
                body['trial_end'] = inputs['trial_end']
            if 'proration_behavior' in inputs and inputs['proration_behavior']:
                body['proration_behavior'] = inputs['proration_behavior']
            if 'metadata' in inputs and inputs['metadata']:
                body['metadata'] = inputs['metadata']

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions/{subscription_id}",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "subscription": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "subscription": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("cancel_subscription")
class CancelSubscriptionAction(ActionHandler):
    """Cancel a subscription immediately or at period end."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            subscription_id = inputs['subscription_id']
            headers = get_common_headers()

            # Check if we should cancel at period end or immediately
            cancel_at_period_end = inputs.get('cancel_at_period_end', False)

            if cancel_at_period_end:
                # Update subscription to cancel at period end
                body = {"cancel_at_period_end": True}
                form_data = build_form_data(body)

                response = await context.fetch(
                    f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions/{subscription_id}",
                    method="POST",
                    headers=headers,
                    data=form_data
                )
            else:
                # Cancel immediately
                body = {}
                if 'cancellation_details' in inputs and inputs['cancellation_details']:
                    body['cancellation_details'] = inputs['cancellation_details']
                if 'invoice_now' in inputs and inputs['invoice_now'] is not None:
                    body['invoice_now'] = inputs['invoice_now']
                if 'prorate' in inputs and inputs['prorate'] is not None:
                    body['prorate'] = inputs['prorate']

                form_data = build_form_data(body) if body else {}

                response = await context.fetch(
                    f"{STRIPE_API_BASE_URL}/{API_VERSION}/subscriptions/{subscription_id}",
                    method="DELETE",
                    headers=headers,
                    data=form_data if form_data else None
                )

            return ActionResult(
                data={
                    "subscription": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "subscription": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Payment Method Action Handlers ----

@stripe.action("list_payment_methods")
class ListPaymentMethodsAction(ActionHandler):
    """Retrieve a paginated list of payment methods for a customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = build_list_params(inputs)

            # Customer is required for listing payment methods
            if 'customer' in inputs and inputs['customer']:
                params['customer'] = inputs['customer']

            # Type is required by Stripe API - default to 'card'
            params['type'] = inputs.get('type', 'card')

            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/payment_methods",
                method="GET",
                headers=headers,
                params=params
            )

            payment_methods = response.get('data', [])

            return ActionResult(
                data={
                    "payment_methods": payment_methods,
                    "has_more": response.get('has_more', False),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "payment_methods": [],
                    "has_more": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("get_payment_method")
class GetPaymentMethodAction(ActionHandler):
    """Retrieve details of a specific payment method by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payment_method_id = inputs['payment_method_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/payment_methods/{payment_method_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "payment_method": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "payment_method": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("attach_payment_method")
class AttachPaymentMethodAction(ActionHandler):
    """Attach a payment method to a customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payment_method_id = inputs['payment_method_id']
            body = {
                "customer": inputs['customer']
            }

            headers = get_common_headers()
            form_data = build_form_data(body)

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/payment_methods/{payment_method_id}/attach",
                method="POST",
                headers=headers,
                data=form_data
            )

            return ActionResult(
                data={
                    "payment_method": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "payment_method": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@stripe.action("detach_payment_method")
class DetachPaymentMethodAction(ActionHandler):
    """Detach a payment method from its attached customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payment_method_id = inputs['payment_method_id']
            headers = get_common_headers()

            response = await context.fetch(
                f"{STRIPE_API_BASE_URL}/{API_VERSION}/payment_methods/{payment_method_id}/detach",
                method="POST",
                headers=headers
            )

            return ActionResult(
                data={
                    "payment_method": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "payment_method": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )
