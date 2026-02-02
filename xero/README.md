# Xero Integration

A comprehensive integration for accessing Xero accounting data including financial reports, contact management, invoice/bill creation and updates, file attachments, and aged payables/receivables through the Xero API.

## Features

### Actions
- **Get Available Connections** - Retrieve all available Xero tenant connections with company names and IDs
- **Find Contact by Name** - Search for contacts by name within a specific tenant using tenant ID
- **Get Invoices** - Retrieve invoices (sales/purchase) with optimized filtering, pagination, and specific invoice lookup using tenant ID
- **Get Invoice PDF** - Download individual invoices as PDF files using tenant ID and invoice ID
- **Create Sales Invoice** - Create new sales invoices (ACCREC) for billing customers using tenant ID
- **Create Purchase Bill** - Create new purchase bills (ACCPAY) for recording supplier invoices using tenant ID
- **Update Sales Invoice** - Update existing sales invoices (DRAFT/SUBMITTED only) using tenant ID
- **Update Purchase Bill** - Update existing purchase bills (DRAFT/SUBMITTED only) using tenant ID
- **Get Aged Payables** - Retrieve aged payables report for specific contacts using tenant ID and contact ID
- **Get Aged Receivables** - Retrieve aged receivables report for specific contacts using tenant ID and contact ID
- **Get Balance Sheet** - Access balance sheet reports with optional period comparisons using tenant ID
- **Get Profit and Loss** - Retrieve P&L statements with flexible date ranges and timeframes using tenant ID
- **Get Trial Balance** - Access trial balance reports with optional payment filtering using tenant ID
- **Get Accounts** - Retrieve chart of accounts to classify line items (revenue, expenses, assets, etc.) using tenant ID
- **Get Payments** - Fetch payment records for invoices/bills (customer receipts, supplier payments, refunds) using tenant ID
- **Get Bank Transactions** - Access bank transactions not tied to invoices (CapEx, financing, operating expenses) using tenant ID
- **Attach File to Invoice** - Attach files to existing sales invoices or purchase bills using tenant ID
- **Attach File to Bill** - Attach files to existing purchase bills using tenant ID
- **Get Attachments** - Retrieve list of all attachments for invoices, bills, or bank transactions using tenant ID
- **Get Attachment Content** - Download actual file content of specific attachments for analysis using tenant ID
- **Get Purchase Orders** - Retrieve purchase orders with filtering and pagination, or fetch a specific purchase order by ID using tenant ID
- **Create Purchase Order** - Create new purchase orders for ordering goods or services from suppliers using tenant ID
- **Update Purchase Order** - Update existing purchase orders (DRAFT/SUBMITTED only) using tenant ID
- **Delete Purchase Order** - Delete purchase orders by updating status to DELETED using tenant ID
- **Get Purchase Order History** - Retrieve history and notes for a specific purchase order using tenant ID
- **Add Note to Purchase Order** - Add notes to purchase order history for tracking and communication using tenant ID

## Setup

### 1. Authentication
The integration uses Xero's OAuth 2.0 authentication:

1. **Create a Xero App**:
   - Go to [Xero Developer Portal](https://developer.xero.com/)
   - Create a new app and configure OAuth 2.0 settings
   - Note your Client ID and Client Secret

2. **Configure Integration**:
   - Set authentication provider to "Xero" 
   - Complete OAuth flow through the platform's auth system
   - Grant necessary permissions to access accounting data

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Required Scopes
The integration requires these OAuth scopes:
- `accounting.reports.read` - Access financial reports
- `accounting.contacts.read` - Access contact information
- `accounting.settings.read` - Access organization settings
- `accounting.transactions.read` - Access transaction data
- `accounting.transactions` - Create and update transactions (invoices, bills)
- `accounting.attachments` - Upload and download file attachments
- `offline_access` - Maintain token refresh capability

## Usage Examples

### Get Available Connections
```python
# Get all available tenant connections
result = await integration.execute_action("get_available_connections", {})

if result['success']:
    for company in result['companies']:
        print(f"Tenant ID: {company['tenant_id']}")
        print(f"Company Name: {company['company_name']}")
```

### Find Contact
```python
# Search for contacts by name using tenant ID
result = await integration.execute_action("find_contact_by_name", {
    "tenant_id": "tenant-guid-123",
    "contact_name": "ABC Suppliers"
})

for contact in result["contacts"]:
    print(f"Contact: {contact['name']} (ID: {contact['contact_id']})")
```

### Get Aged Payables Report
```python
# Get aged payables for a specific contact using tenant ID
result = await integration.execute_action("get_aged_payables", {
    "tenant_id": "tenant-guid-123",
    "contact_id": "contact-guid-456",
    "date": "2025-01-31"
})

for report in result["reports"]:
    print(f"Report: {report['report_name']} - {report['report_date']}")
```

### Get Invoices
```python
# Get all authorized invoices for a specific date range using tenant ID
result = await integration.execute_action("get_invoices", {
    "tenant_id": "tenant-guid-123",
    "where": "Status==\"AUTHORISED\" AND Date>=DateTime(2025,01,01)",
    "order": "Date DESC",
    "pageSize": 50
})

for invoice in result["Invoices"]:
    print(f"Invoice: {invoice['InvoiceNumber']} - {invoice['Total']} - {invoice['Contact']['Name']}")

# Get a specific invoice by ID
result = await integration.execute_action("get_invoices", {
    "tenant_id": "tenant-guid-123",
    "invoice_id": "243216c5-369e-4056-ac67-05388f86dc81"
})

invoice = result["Invoices"][0]
print(f"Invoice Details: {invoice['InvoiceNumber']} - Status: {invoice['Status']}")
```

### Get Invoice as PDF
```python
# Download a specific invoice as PDF using tenant ID and invoice ID
result = await integration.execute_action("get_invoice_pdf", {
    "tenant_id": "tenant-guid-123",
    "invoice_id": "243216c5-369e-4056-ac67-05388f86dc81"
})

if result["success"]:
    pdf_file = result["file"]
    print(f"Downloaded PDF: {pdf_file['name']}")
    print(f"Content Type: {pdf_file['contentType']}")

    # Save the PDF to disk
    import base64
    pdf_bytes = base64.b64decode(pdf_file['content'])
    with open(pdf_file['name'], 'wb') as f:
        f.write(pdf_bytes)
    print(f"Saved to {pdf_file['name']}")

# Example: Download multiple overdue invoices as PDFs
overdue_result = await integration.execute_action("get_invoices", {
    "tenant_id": "tenant-guid-123",
    "where": "Status==\"AUTHORISED\" AND DueDate<DateTime.Today",
    "pageSize": 10
})

for invoice in overdue_result["Invoices"]:
    pdf_result = await integration.execute_action("get_invoice_pdf", {
        "tenant_id": "tenant-guid-123",
        "invoice_id": invoice["InvoiceID"]
    })
    if pdf_result["success"]:
        print(f"Downloaded PDF for invoice {invoice['InvoiceNumber']}")
```

### Get Balance Sheet
```python
# Get current balance sheet with 3-month comparison using tenant ID
result = await integration.execute_action("get_balance_sheet", {
    "tenant_id": "tenant-guid-123",
    "date": "2025-01-31",
    "periods": 3
})

for report in result["reports"]:
    print(f"Balance Sheet as of {report['report_date']}")
```

### Get Profit & Loss Statement
```python
# Get P&L for specific date range using tenant ID
result = await integration.execute_action("get_profit_and_loss", {
    "tenant_id": "tenant-guid-123",
    "from_date": "2025-01-01",
    "to_date": "2025-01-31",
    "timeframe": "MONTH",
    "periods": 3
})

for report in result["reports"]:
    print(f"P&L Report: {report['report_name']}")
```

### Get Accounts
```python
# Get chart of accounts for line item classification using tenant ID
result = await integration.execute_action("get_accounts", {
    "tenant_id": "tenant-guid-123",
    "where": "Status==\"ACTIVE\"",
    "order": "Code ASC"
})

for account in result["Accounts"]:
    print(f"Account: {account['Name']} ({account['Code']}) - Type: {account['Type']}")
```

### Get Payments
```python
# Get payment records with date filtering using tenant ID
result = await integration.execute_action("get_payments", {
    "tenant_id": "tenant-guid-123",
    "where": "Date>=DateTime(2025,01,01) AND Date<=DateTime(2025,01,31)",
    "order": "Date DESC"
})

for payment in result["Payments"]:
    print(f"Payment: {payment['Amount']} on {payment['Date']} - Status: {payment['Status']}")
```

### Get Bank Transactions
```python
# Get bank transactions not tied to invoices using tenant ID
result = await integration.execute_action("get_bank_transactions", {
    "tenant_id": "tenant-guid-123",
    "where": "Date>=DateTime(2025,01,01)",
    "order": "Date DESC",
    "page": 1
})

for transaction in result["BankTransactions"]:
    print(f"Transaction: {transaction['Total']} - {transaction['Reference']}")
```

### Create Sales Invoice
```python
# Create a new sales invoice using tenant ID
result = await integration.execute_action("create_sales_invoice", {
    "tenant_id": "tenant-guid-123",
    "contact": {"ContactID": "contact-guid-456"},
    "line_items": [{
        "Description": "Consulting Services",
        "Quantity": 5,
        "UnitAmount": 150.00,
        "AccountCode": "200",
        "TaxType": "OUTPUT"
    }],
    "date": "2025-01-31",
    "due_date": "2025-02-28",
    "status": "DRAFT"
})

invoice = result["Invoices"][0]
print(f"Created Invoice: {invoice['InvoiceNumber']} - Total: {invoice['Total']}")
```

### Create Purchase Bill
```python
# Create a new purchase bill using tenant ID
result = await integration.execute_action("create_purchase_bill", {
    "tenant_id": "tenant-guid-123",
    "contact": {"ContactID": "supplier-guid-789"},
    "line_items": [{
        "Description": "Office Supplies",
        "Quantity": 1,
        "UnitAmount": 250.00,
        "AccountCode": "400",
        "TaxType": "INPUT"
    }],
    "date": "2025-01-31",
    "invoice_number": "SUPP-001",
    "status": "AUTHORISED"
})

bill = result["Invoices"][0]
print(f"Created Bill: {bill['InvoiceNumber']} - Total: {bill['Total']}")
```

### Attach File to Invoice
```python
# Attach a PDF receipt to an existing invoice using tenant ID
import base64

# Read file and encode to base64
with open("receipt.pdf", "rb") as f:
    file_content = base64.b64encode(f.read()).decode('utf-8')

result = await integration.execute_action("attach_file_to_invoice", {
    "tenant_id": "tenant-guid-123",
    "invoice_id": "invoice-guid-456",
    "file": {
        "content": file_content,
        "name": "receipt.pdf",
        "contentType": "application/pdf"
    },
    "include_online": True
})

attachment = result["Attachments"][0]
print(f"Attached file: {attachment['FileName']} - Size: {attachment['ContentLength']} bytes")
```

### Get Attachments List
```python
# Get all attachments for an invoice using tenant ID
result = await integration.execute_action("get_attachments", {
    "tenant_id": "tenant-guid-123",
    "endpoint": "Invoices",
    "guid": "invoice-guid-456"
})

for attachment in result["Attachments"]:
    print(f"Attachment: {attachment['FileName']} - Type: {attachment['MimeType']}")
```

### Download Attachment Content
```python
# Download the actual file content of an attachment using tenant ID
result = await integration.execute_action("get_attachment_content", {
    "tenant_id": "tenant-guid-123",
    "endpoint": "Invoices",
    "guid": "invoice-guid-456",
    "file_name": "receipt.pdf"
})

if result["success"]:
    file_data = result["file"]
    print(f"Downloaded: {file_data['name']} - Content Type: {file_data['contentType']}")
    # file_data['content'] contains base64 encoded file content
```

### Get Purchase Orders
```python
# Get all authorized purchase orders for a specific date range using tenant ID
result = await integration.execute_action("get_purchase_orders", {
    "tenant_id": "tenant-guid-123",
    "where": "Status==\"AUTHORISED\" AND Date>=DateTime(2025,01,01)",
    "order": "Date DESC",
    "page": 1
})

for po in result["PurchaseOrders"]:
    print(f"PO: {po['PurchaseOrderNumber']} - {po['Total']} - {po['Contact']['Name']}")

# Get a specific purchase order by ID
result = await integration.execute_action("get_purchase_orders", {
    "tenant_id": "tenant-guid-123",
    "purchase_order_id": "po-guid-456"
})

po = result["PurchaseOrders"][0]
print(f"PO Details: {po['PurchaseOrderNumber']} - Status: {po['Status']}")
```

### Create Purchase Order
```python
# Create a new purchase order using tenant ID
result = await integration.execute_action("create_purchase_order", {
    "tenant_id": "tenant-guid-123",
    "contact": {"ContactID": "supplier-guid-789"},
    "line_items": [{
        "Description": "Office Equipment",
        "Quantity": 2,
        "UnitAmount": 500.00,
        "AccountCode": "630",
        "TaxType": "INPUT"
    }],
    "date": "2025-01-31",
    "delivery_date": "2025-02-15",
    "reference": "PO-2025-001",
    "status": "DRAFT",
    "delivery_address": "123 Main St, City, State 12345",
    "attention_to": "John Smith",
    "telephone": "+1-555-0123",
    "delivery_instructions": "Please call before delivery"
})

po = result["PurchaseOrders"][0]
print(f"Created PO: {po['PurchaseOrderNumber']} - Total: {po['Total']}")
```

### Update Purchase Order
```python
# Update an existing purchase order using tenant ID
result = await integration.execute_action("update_purchase_order", {
    "tenant_id": "tenant-guid-123",
    "purchase_order_id": "po-guid-456",
    "status": "AUTHORISED",
    "reference": "PO-2025-001-UPDATED",
    "delivery_date": "2025-02-20"
})

po = result["PurchaseOrders"][0]
print(f"Updated PO: {po['PurchaseOrderNumber']} - Status: {po['Status']}")
```

### Add Note to Purchase Order
```python
# Add a note to a purchase order's history using tenant ID
result = await integration.execute_action("add_note_to_purchase_order", {
    "tenant_id": "tenant-guid-123",
    "purchase_order_id": "po-guid-456",
    "note": "Supplier confirmed delivery date. Items will arrive on Feb 20th."
})

history = result["HistoryRecords"][0]
print(f"Added note: {history['Details']}")
```

### Get Purchase Order History
```python
# Get history and notes for a purchase order using tenant ID
result = await integration.execute_action("get_purchase_order_history", {
    "tenant_id": "tenant-guid-123",
    "purchase_order_id": "po-guid-456"
})

for record in result["HistoryRecords"]:
    print(f"{record['DateUTC']}: {record['Details']}")
```

### Delete Purchase Order
```python
# Delete a purchase order by setting status to DELETED using tenant ID
result = await integration.execute_action("delete_purchase_order", {
    "tenant_id": "tenant-guid-123",
    "purchase_order_id": "po-guid-456"
})

po = result["PurchaseOrders"][0]
print(f"Deleted PO: {po['PurchaseOrderNumber']} - Status: {po['Status']}")
```

## Testing

### API Testing with Postman

Before implementing the integration, you can test Xero API access using Postman:

1. **Setup OAuth 2.0 Authentication**:
   - In Postman, go to Authorization tab
   - Select "OAuth 2.0" as type
   - Configure with your Xero app credentials
   - Use authorization URL: `https://login.xero.com/identity/connect/authorize`
   - Use token URL: `https://identity.xero.com/connect/token`
   - Add required scopes: `accounting.reports.read`, `accounting.contacts.read`, `accounting.transactions`, `accounting.attachments`, `offline_access`

2. **Test Key Endpoints**:
   - **Get Connections**: `GET https://api.xero.com/connections`
   - **Find Contacts**: `GET https://api.xero.com/api.xro/2.0/Contacts?where=Name.Contains("contact_name")`
   - **Get Invoices**: `GET https://api.xero.com/api.xro/2.0/Invoices`
   - **Create Invoice**: `POST https://api.xero.com/api.xro/2.0/Invoices`
   - **Aged Payables**: `GET https://api.xero.com/api.xro/2.0/Reports/AgedPayablesByContact?contactId={contact_id}`
   - **Aged Receivables**: `GET https://api.xero.com/api.xro/2.0/Reports/AgedReceivablesByContact?contactId={contact_id}`
   - **Get Attachments**: `GET https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments`
   - **Upload Attachment**: `POST https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}`

3. **Required Headers**:
   - `Accept: application/json`
   - `xero-tenant-id: {tenant_id}` (from connections response)

This helps validate API access and understand response structures before coding the integration.

### Quick Test
```bash
# Run basic tests
cd tests
python test_xero.py
```

### Test Structure
```python
# Example test for getting available connections
async def test_get_available_connections():
    auth = {}  # OAuth tokens handled automatically
    inputs = {}
    
    async with ExecutionContext(auth=auth) as context:
        result = await xero.execute_action("get_available_connections", inputs, context)
        assert result["success"] == True
        assert "companies" in result
```

## API Reference

### Actions

#### `get_available_connections`
Get all available Xero tenant connections with company names and IDs.

**Input:**
- No input parameters required

**Output:**
- `success`: Boolean indicating if request was successful
- `companies`: Array of company objects with tenant_id and company_name
- `message`: Error message if success is false

#### `get_invoices`
Retrieve invoices from Xero API with optimized filtering and pagination.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `invoice_id` (optional): Specific invoice ID (GUID) to fetch
- `where` (optional): Filter clause with optimized fields (Status=="AUTHORISED", Date>=DateTime(2020,01,01), Contact.ContactID==guid("id"), Type=="ACCREC", Total>=100.00)
- `order` (optional): Sort parameter (InvoiceNumber ASC, Date DESC, Total DESC,Date ASC)
- `page` (optional): Page number for pagination
- `pageSize` (optional): Page size for pagination (max 100)
- `statuses` (optional): Comma-separated status list (DRAFT,SUBMITTED,AUTHORISED)
- `invoice_numbers` (optional): Comma-separated invoice numbers for bulk retrieval
- `contact_ids` (optional): Comma-separated contact IDs for filtering

**Output:**
- `invoices`: Array containing Xero invoice objects with invoice details, line items, and contact information

#### `get_invoice_pdf`
Download a specific invoice as a PDF file from Xero API. Works with both sales invoices (ACCREC) and purchase bills (ACCPAY).

**Input:**
- `tenant_id` (required): Xero tenant ID
- `invoice_id` (required): Invoice ID (GUID) to retrieve as PDF

**Output:**
- `file`: Object containing name, content (base64 encoded), and contentType (application/pdf)
- `success`: Boolean indicating if download was successful
- `error`: Error message if download failed

**Use Cases:**
- Download overdue invoices for customer follow-up
- Archive invoices for record-keeping
- Generate invoice reports for accounting purposes
- Export invoices for external systems

**Example Workflow:**
1. Use `get_invoices` with filters to find specific invoices (e.g., overdue, by status)
2. Extract invoice IDs from the response
3. Call `get_invoice_pdf` for each invoice ID to download PDFs
4. Decode base64 content and save to disk or send via email

#### `find_contact_by_name`
Search for contacts by name within a tenant.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact_name` (required): Contact name to search for

**Output:**
- `contacts`: Array of matching contact objects with ID, name, and status

#### `get_aged_payables`
Retrieve aged payables report for a specific contact.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact_id` (required): Contact ID (GUID)
- `date` (optional): Report date (YYYY-MM-DD format)

**Output:**
- `reports`: Array containing Xero aged payables report data

#### `get_aged_receivables`
Retrieve aged receivables report for a specific contact.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact_id` (required): Contact ID (GUID)
- `date` (optional): Report date (YYYY-MM-DD format)

**Output:**
- `reports`: Array containing Xero aged receivables report data

#### `get_balance_sheet`
Access balance sheet report with optional period comparisons.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `date` (optional): Report date (YYYY-MM-DD format)
- `periods` (optional): Number of periods to compare (1-12)

**Output:**
- `reports`: Array containing balance sheet report data

#### `get_profit_and_loss`
Retrieve profit and loss statement with flexible parameters.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `date` (optional): Report date (YYYY-MM-DD format)
- `from_date` (optional): Period start date
- `to_date` (optional): Period end date
- `timeframe` (optional): Period type ("MONTH", "QUARTER", "YEAR")
- `periods` (optional): Number of periods to compare (1-12)

**Output:**
- `reports`: Array containing P&L report data

#### `get_trial_balance`
Access trial balance report with payment filtering options.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `date` (optional): Report date (defaults to last month end)
- `payments_only` (optional): Include only payments (boolean)

**Output:**
- `reports`: Array containing trial balance report data

#### `get_accounts`
Retrieve chart of accounts to classify line items by type (revenue, expenses, assets, etc.).

**Input:**
- `tenant_id` (required): Xero tenant ID
- `where` (optional): Filter clause for accounts (e.g., Status=="ACTIVE")
- `order` (optional): Sort parameter (e.g., Code ASC)

**Output:**
- `accounts`: Array containing Xero account objects with ID, name, code, type, and status

#### `get_payments`
Fetch payment records for invoices and bills including customer receipts and supplier payments.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `where` (optional): Filter clause for date ranges (e.g., Date>=DateTime(2025,01,01))
- `order` (optional): Sort parameter (e.g., Date DESC)

**Output:**
- `payments`: Array containing Xero payment objects with amount, date, status, and references

#### `get_bank_transactions`
Access bank transactions not tied to invoices, covering CapEx, financing, and other operating expenses.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `where` (optional): Filter clause for date ranges
- `order` (optional): Sort parameter
- `page` (optional): Page number for pagination

**Output:**
- `bank_transactions`: Array containing Xero bank transaction objects with amounts, references, and line items

#### `create_sales_invoice`
Create a new sales invoice (ACCREC) in Xero for billing customers.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact` (required): Contact object with ContactID or Name
- `line_items` (required): Array of line items with Description, UnitAmount, AccountCode, and optional Quantity/TaxType
- `date` (optional): Invoice date (YYYY-MM-DD format)
- `due_date` (optional): Due date for payment
- `invoice_number` (optional): Custom invoice number
- `reference` (optional): Invoice reference
- `status` (optional): Invoice status (DRAFT, SUBMITTED, AUTHORISED)

**Output:**
- `Invoices`: Array containing the created invoice with full details including InvoiceID, InvoiceNumber, Total, and Status

#### `create_purchase_bill`
Create a new purchase bill (ACCPAY) in Xero for recording supplier invoices.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact` (required): Contact object with ContactID or Name
- `line_items` (required): Array of line items with Description, UnitAmount, AccountCode, and optional Quantity/TaxType
- `date` (optional): Bill date (YYYY-MM-DD format)
- `due_date` (optional): Due date for payment
- `invoice_number` (optional): Supplier's invoice/bill number
- `reference` (optional): Bill reference
- `status` (optional): Bill status (DRAFT, SUBMITTED, AUTHORISED)

**Output:**
- `Invoices`: Array containing the created purchase bill with full details

#### `update_sales_invoice`
Update an existing sales invoice (ACCREC) in Xero. Only DRAFT and SUBMITTED invoices can be updated.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `invoice_id` (required): ID of the invoice to update (GUID)
- `contact` (optional): Contact object to update
- `line_items` (optional): Array of line items to replace existing ones
- `date` (optional): Invoice date
- `status` (optional): Invoice status

**Output:**
- `Invoices`: Array containing the updated invoice with full details

#### `update_purchase_bill`
Update an existing purchase bill (ACCPAY) in Xero. Only DRAFT and SUBMITTED bills can be updated.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `invoice_id` (required): ID of the bill to update (GUID)
- `contact` (optional): Contact object to update
- `line_items` (optional): Array of line items to replace existing ones
- `date` (optional): Bill date
- `status` (optional): Bill status

**Output:**
- `Invoices`: Array containing the updated purchase bill with full details

#### `attach_file_to_invoice`
Attach a file to an existing sales invoice or purchase bill in Xero.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `invoice_id` (required): ID of the invoice/bill to attach file to (GUID)
- `file` (required): File object with content (base64), name, and contentType
- `include_online` (optional): Whether to include attachment in online invoice (default: true)

**Output:**
- `Attachments`: Array containing attachment details including FileName, ContentLength, and AttachmentID

#### `attach_file_to_bill`
Attach a file to an existing purchase bill in Xero.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `bill_id` (required): ID of the bill to attach file to (GUID)
- `file` (required): File object with content (base64), name, and contentType
- `include_online` (optional): Whether to include attachment in online bill (default: true)

**Output:**
- `Attachments`: Array containing attachment details including FileName, ContentLength, and AttachmentID

#### `get_attachments`
Get all attachments for a specific invoice, bill, or bank transaction from Xero API.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `endpoint` (required): The endpoint type ("Invoices", "Bills", "BankTransactions")
- `guid` (required): The GUID of the invoice/bill/transaction

**Output:**
- `Attachments`: Array of attachment metadata including AttachmentID, FileName, Url, MimeType, and ContentLength

#### `get_attachment_content`
Download the actual content of a specific attachment from Xero API for analysis.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `endpoint` (required): The endpoint type ("Invoices", "Bills", "BankTransactions")
- `guid` (required): The GUID of the invoice/bill/transaction
- `file_name` (required): The filename of the attachment to download

**Output:**
- `file`: Object containing name, content (base64), and contentType
- `success`: Boolean indicating if download was successful
- `error`: Error message if download failed

#### `get_purchase_orders`
Retrieve purchase orders from Xero API with filtering and pagination. Can fetch all purchase orders or a specific one by ID.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `purchase_order_id` (optional): Specific purchase order ID (GUID) to fetch
- `where` (optional): Filter clause (Status=="AUTHORISED", Date>=DateTime(2020,01,01), Contact.ContactID==guid("id"))
- `order` (optional): Sort parameter (Date DESC, PurchaseOrderNumber ASC)
- `page` (optional): Page number for pagination
- `statuses` (optional): Comma-separated status list (DRAFT,SUBMITTED,AUTHORISED,BILLED)

**Output:**
- `PurchaseOrders`: Array of Xero purchase order objects with details including PurchaseOrderNumber, Date, Contact, LineItems, and Status

#### `create_purchase_order`
Create a new purchase order in Xero for ordering goods or services from suppliers.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `contact` (required): Contact object with ContactID or Name
- `line_items` (required): Array of line items with Description, UnitAmount, AccountCode, and optional Quantity/TaxType
- `date` (optional): Purchase order date (YYYY-MM-DD format)
- `delivery_date` (optional): Expected delivery date (YYYY-MM-DD format)
- `purchase_order_number` (optional): Custom purchase order number
- `reference` (optional): Purchase order reference
- `currency_code` (optional): Currency code (defaults to organization currency)
- `status` (optional): PO status (DRAFT, SUBMITTED, AUTHORISED, BILLED, DELETED)
- `delivery_address` (optional): Delivery address string
- `attention_to` (optional): Name of person to be contacted
- `telephone` (optional): Phone number for contact
- `delivery_instructions` (optional): Delivery instructions

**Output:**
- `PurchaseOrders`: Array containing the created purchase order with full details including PurchaseOrderID, PurchaseOrderNumber, Total, and Status

#### `update_purchase_order`
Update an existing purchase order in Xero. Only DRAFT and SUBMITTED purchase orders can be updated.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `purchase_order_id` (required): ID of the purchase order to update (GUID)
- `contact` (optional): Contact object to update
- `line_items` (optional): Array of line items to update (provide LineItemID to update existing, omit to create new, exclude existing to delete)
- `date` (optional): Purchase order date
- `delivery_date` (optional): Expected delivery date
- `status` (optional): Purchase order status
- `reference` (optional): Purchase order reference
- `delivery_address` (optional): Delivery address
- `attention_to` (optional): Contact person name
- `telephone` (optional): Contact phone number
- `delivery_instructions` (optional): Delivery instructions

**Output:**
- `PurchaseOrders`: Array containing the updated purchase order with full details

#### `delete_purchase_order`
Delete a purchase order in Xero by updating its status to DELETED.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `purchase_order_id` (required): ID of the purchase order to delete (GUID)

**Output:**
- `PurchaseOrders`: Array containing the deleted purchase order with updated status (DELETED)

#### `get_purchase_order_history`
Retrieve the history and notes for a specific purchase order from Xero API.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `purchase_order_id` (required): ID of the purchase order to get history for (GUID)

**Output:**
- `HistoryRecords`: Array of history records including Details, DateUTC, and User information

#### `add_note_to_purchase_order`
Add a note to a purchase order's history in Xero for tracking and communication.

**Input:**
- `tenant_id` (required): Xero tenant ID
- `purchase_order_id` (required): ID of the purchase order to add note to (GUID)
- `note` (required): The note text to add to the purchase order history

**Output:**
- `HistoryRecords`: Array containing the added history record with Details and DateUTC

## Rate Limiting

The integration handles rate limit errors from the Xero API:

### Features
- **Automatic retry**: Retries requests on HTTP 429 errors
- **Configurable delays**: Uses Retry-After headers or 60-second default
- **Maximum retries**: Attempts up to 3 retries before failing

### Implementation
- Monitors API responses for rate limit errors
- Automatically retries failed requests with delays
- Non-rate-limit errors are passed through immediately

## Error Handling

The integration includes comprehensive error handling:
- Invalid company names return descriptive error messages
- Missing contacts result in empty arrays rather than errors
- Network issues are handled gracefully with informative errors
- Authentication problems provide clear guidance for resolution
- All API responses are validated before returning data
- Rate limit errors trigger automatic retry with appropriate delays
- File upload/download errors provide detailed failure information
- Invoice/bill creation validation errors with field-specific messages

## Development

### Project Structure
```
xero/
├── config.json          # Integration configuration
├── requirements.txt     # Python dependencies  
├── xero.py             # Main integration code
├── icon.png            # Integration icon
├── README.md           # This file
└── tests/
    ├── __init__.py
    ├── context.py      # Test context setup
    └── test_xero.py    # Test suite
```

### Adding New Features
1. Update `config.json` with new action definitions
2. Add implementation in `xero.py` with matching decorators
3. Add corresponding tests in `tests/test_xero.py`
4. Update this documentation

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify OAuth app is properly configured in Xero
   - Ensure required scopes are granted
   - Check token refresh is working properly

2. **Tenant Not Found**
   - Verify company name exactly matches Xero tenant name
   - Check user has access to the specified organization
   - Ensure company is properly connected to Xero

3. **Contact Not Found**  
   - Verify contact exists in the specified tenant
   - Check contact name spelling and formatting
   - Ensure contact is active (not archived)

4. **Empty Reports**
   - Check date ranges are valid
   - Verify contact has transactions in the specified period
   - Ensure user has appropriate permissions to view reports

### Debug Tips
- Use exact company names as they appear in Xero
- Contact names are case-insensitive but must be exact matches
- Date parameters should be in YYYY-MM-DD format
- All reports return raw Xero API response data for maximum flexibility

## Support

For issues related to:
- **Integration bugs**: Check the test suite and error logs
- **Xero API**: Consult [Xero API documentation](https://developer.xero.com/documentation/)
- **Authentication**: Verify OAuth app configuration and permissions
- **Data access**: Ensure proper user permissions and organization access