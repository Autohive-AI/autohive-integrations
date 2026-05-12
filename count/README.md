# Count

Count is a modern accounting platform built for startups and SMBs. This integration provides 43 actions covering chart of accounts, customers, vendors, products, transactions, invoices, bills, journal entries, tags, and financial reports.

## Auth Setup

Count uses OAuth 2.0. You'll need a Client ID and Client Secret from the [Count Developer Portal](https://developers.getcount.com).

1. Register your application at developers.getcount.com
2. Set your redirect URI in the app settings
3. Initiate the OAuth flow: `GET https://dev-api.getcount.com/auth2/authorize-initiate?clientId=...&redirectUri=...`
4. Exchange the authorization code for an access token: `POST https://dev-api.getcount.com/partners/grant-access-token`
5. Use the returned `accessToken` as the Bearer token for all API calls

## Actions

| Action | Description | Key Inputs | Key Outputs |
|--------|-------------|------------|-------------|
| `list_accounts` | List chart of accounts | page, limit | accounts[] |
| `create_account` | Add a new account | name, type | account |
| `update_account` | Update an account | account_uuid | account |
| `delete_account` | Delete an account | account_uuid | deleted |
| `list_customers` | List all customers | search, page, limit | customers[] |
| `get_customer` | Get a customer by UUID | customer_uuid | customer |
| `find_customer_by_email` | Find customer by email | email | customer |
| `create_customer` | Add a new customer | name | customer |
| `update_customer` | Update a customer | customer_uuid | customer |
| `delete_customer` | Delete a customer | customer_uuid | deleted |
| `list_vendors` | List all vendors | search, page, limit | vendors[] |
| `create_vendor` | Add a new vendor | name | vendor |
| `update_vendor` | Update a vendor | vendor_uuid | vendor |
| `delete_vendor` | Delete a vendor | vendor_uuid | deleted |
| `list_products` | List products/services | search, page, limit | products[] |
| `get_product` | Get a product by UUID | product_uuid | product |
| `find_product_by_name` | Find product by name | name | product |
| `create_product` | Add a new product | name | product |
| `update_product` | Update a product | product_uuid | product |
| `delete_product` | Delete a product | product_uuid | deleted |
| `list_transactions` | List all transactions | page, limit, startDate, endDate | transactions[] |
| `create_transaction` | Create a transaction | date, amount, accountUuid | transaction |
| `update_transaction` | Update a transaction | transaction_uuid | transaction |
| `delete_transaction` | Delete a transaction | transaction_uuid | deleted |
| `get_invoice` | Get an invoice | invoice_uuid | invoice |
| `create_invoice` | Create an invoice | customerUuid, invoiceNumber, date, dueDate, invoiceType, products | invoice |
| `update_invoice` | Update an invoice | invoice_uuid | invoice |
| `delete_invoice` | Delete an invoice | invoice_uuid | deleted |
| `create_bill` | Add a bill | vendorUuid, date, dueDate, products | bill |
| `update_bill` | Update a bill | bill_uuid | bill |
| `delete_bill` | Delete a bill | bill_uuid | deleted |
| `approve_bill` | Approve a bill | bill_uuid | bill |
| `list_journal_entries` | List journal entries | page, limit | journal_entries[] |
| `create_journal_entry` | Add a journal entry | date, lines | journal_entry |
| `update_journal_entry` | Update a journal entry | journal_entry_uuid | journal_entry |
| `delete_journal_entry` | Delete a journal entry | journal_entry_uuid | deleted |
| `list_tags` | List all tags | page, limit | tags[] |
| `create_tag` | Create a tag | name | tag |
| `update_tag` | Update a tag | tag_uuid | tag |
| `delete_tag` | Delete a tag | tag_uuid | deleted |
| `get_trial_balance` | Get trial balance report | startDate, endDate | report |
| `get_balance_sheet` | Get balance sheet report | date | report |
| `get_profit_and_loss` | Get profit & loss report | startDate, endDate | report |

## API Info

- **Base URL:** `https://api.getcount.com`
- **Dev Base URL:** `https://dev-api.getcount.com`
- **Docs:** https://developers.getcount.com
- **Auth:** OAuth 2.0 Authorization Code flow

## Troubleshooting

- **401 Unauthorized:** Access token is expired — refresh using `partners/refresh-user-access-token`
- **400 Bad Request:** Check required fields; for invoices, ensure `customerUuid` exists and email is unique
- **404 Not Found:** The UUID provided does not exist in the workspace
