# Microsoft Dynamics 365 Business Central

Read-only Business Central Online integration with 34 actions for inventory planning, client billing, receivables/payables aging and financial reporting. Uses standard REST API v2.0 and platform-managed OAuth. No purchase orders, postings or payments are created.

## Connection setup

An Autohive administrator must configure the **Microsoft Business Central** OAuth provider before this integration can be connected. Declaring it in `config.json` does not create a provider or an Entra registration.

`oauth-provider.example.json` contains the provider's **details** JSON for a provider named `Microsoft Business Central` with auth type `PlatformOauth2`. The public Entra client ID `ef1b00c7-e2bd-43bd-8432-25dd3e278c0b` is stored directly in `client_id`, following the existing auth-provider scripts. Only the client secret is resolved from the SSM SecureString `/integrations/microsoft-business-central/client-secret`; do not configure `client_id_secret_name`. The JSON file is a configuration reference, not an automatic import or deployment script. The backend provider migration is `scripts/20261123.00.add-microsoft-business-central-auth-provider.sql` in the Autohive platform repository.

1. Register a dedicated Microsoft Entra web application. For a shared connection experience, support organizational tenants; for a single customer, tenant-specific authorization/token endpoints can be used.
2. Add **Dynamics 365 Business Central → Delegated permissions → Financials.ReadWrite.All**. The API permission name includes write access; this integration exposes only reads. Restrict the connected user's Business Central object/company permissions to the intended read access.
3. Register the exact callback URL from the target Autohive deployment: `<platform-origin>/integrations/oauth2/callback`.
4. Provision the application client secret through the platform's secret store. Configure the provider's client ID, secret reference, authorization endpoint, token endpoint and scopes. Use the existing Microsoft platform OAuth flow, including refresh-token storage; keep app secrets out of this repository.
5. Configure both provider and integration scopes as `offline_access` and `https://api.businesscentral.dynamics.com/Financials.ReadWrite.All`. Provider scopes drive consent; changing only the integration config is insufficient.
6. Connect a licensed Business Central user with access to the intended sandbox/company. Obtain admin consent when required by tenant policy.

For an organizational multitenant app, authorization and token endpoints are `https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize` and `https://login.microsoftonline.com/organizations/oauth2/v2.0/token`. For a fixed tenant, replace `organizations` with that tenant GUID in both endpoints. Validate consent and token refresh against a sandbox before publishing.

Microsoft Graph access tokens from Microsoft 365 are not Business Central tokens. This integration requires the Business Central resource audience. Application/client-credentials authentication is a separate future option: the platform's generic OAuth lifecycle uses refresh tokens, so a provider row alone does not implement S2S renewal.

Human setup still required: Entra registration/consent, provider and secret-store configuration, a test user with BC permissions, sandbox tenant/environment/company IDs, and customer reconciliation of results. No app registration or provider has been created by adding these files.

## Common inputs and outputs

Every action requires `tenant_id` (GUID) and `environment` (for example `Sandbox`). All except `list_companies` also require `company_id`. Use `list_companies` to select the company explicitly. The API root is `https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/{environment}/api/v2.0`.

Collection actions accept `page_size` (1–1000, default 100) and `next_link`. They return `{records, count, next_link, has_more}`. Use server-driven paging until `has_more` is false; keep the same action, tenant, environment and company. Continuation URLs retain the original filters and are validated against the selected resource. `page_size` uses `Prefer: odata.maxpagesize`, not a total-result `$top` cap. Get-record actions return `{record}`. Provider fields, including units, currencies, document status and partial receipts/shipments, are preserved.

| Action | Additional inputs | Output/use |
|---|---|---|
| `list_companies` | Paging | Accessible company IDs and names. |
| `get_company_information` | Paging | Company details, including local `currencyCode`; returned as a collection. |
| `list_items` | Optional `item_number`; paging | Catalogue, current company-wide `inventory`, recorded `unitCost`, base units. |
| `get_item` | Required `item_id` | One item, including inventory/cost. |
| `list_locations` | Paging | Location names/IDs, not stock balances. |
| `list_item_variants` | Optional `item_id`; paging | Variant codes and IDs. |
| `list_units_of_measure` | Paging | Unit reference codes, not item-specific pack conversions. |
| `list_vendors` | Optional `vendor_number`; paging | Supplier reference data. |
| `list_item_ledger_entries` | Optional `item_number`, `start_date`, `end_date`; paging | Movements, quantities and recorded actual costs; dates filter `postingDate`. |
| `list_purchase_orders` | Optional `vendor_id`, dates; paging | Purchase commitments; dates filter `orderDate`. |
| `get_purchase_order` | Required `purchase_order_id` | Header including vendor, currency and status. |
| `list_purchase_order_lines` | Required `purchase_order_id`; optional `item_id`; paging | Costs, expected receipts, quantities and units. |
| `list_sales_orders` | Optional dates; paging | Sales commitments; dates filter `orderDate`. |
| `get_sales_order` | Required `sales_order_id` | Header and status. |
| `list_sales_order_lines` | Required `sales_order_id`; optional `item_id`; paging | Quantities, shipped quantities and shipment dates. |
| `list_purchase_invoices` | Optional `vendor_id`, dates; paging | Invoice history; dates filter `postingDate`. Inspect document status. |
| `list_purchase_invoice_lines` | Required `purchase_invoice_id`; optional `item_id`; paging | Historical costs, discounts, units and taxes. Join parent currency/status. |
| `estimate_reorder_cost` | Required `item_id`, positive `quantity` in base units | Decimal-string quantity, unit cost and estimated cost, local currency, base unit, cost basis and limitations. |
| `forecast_stock` | Required `item_id`, `start_date`, `end_date`, `forecast_days` (1–365) | Demand baseline, current/projected inventory, days of cover, source counts, dates, method and limitations. Numeric calculations return decimal strings. |

Dates use `YYYY-MM-DD`, inclusive. IDs are GUIDs, not visible document/item numbers. Errors return `ActionError` with sanitized setup/retry guidance. Reads retry transient 429/502/503/504 failures at most twice; long `Retry-After` delays return an error so the workflow can retry later. SDK network retries also apply.

## Finance actions

These reads support recruitment/labour-hire finance workflows: client billing checks, collections worklists, supplier liabilities and accounting analysis across configured business units. They expose standard accounting data; customer-specific brands, branch codes, payroll accounts and legal entities are not hardcoded.

All use the common tenant/environment/company inputs above. Collections return `{records, count, next_link, has_more}`; single-record reads return `{record}`. No additional OAuth scopes are requested, but the connected user's BC permission sets must cover the finance objects being read.

| Action | Additional inputs | Output/use |
|---|---|---|
| `list_customers` | Optional `customer_number`; paging | Customer IDs, balances, credit limits and payment-term IDs. |
| `get_customer` | Required `customer_id` | One billing customer's details. |
| `list_sales_invoices` | Optional `customer_id`, posting dates, `status`, `due_before`, `outstanding_only`; paging | Client invoice totals, due dates, remaining amounts, currency and status. |
| `get_sales_invoice` | Required `sales_invoice_id` | One invoice header for billing investigation. |
| `list_sales_invoice_lines` | Required `sales_invoice_id`; paging | All billing lines, including services/resources/accounts, discounts and tax. |
| `list_sales_credit_memos` | Optional `customer_id`, dates; paging | Billing corrections/credits; dates filter `creditMemoDate`. |
| `list_accounts` | Optional `account_number`; paging | Chart of accounts for agreed revenue, labour-cost and overhead mappings. |
| `list_general_ledger_entries` | Optional `account_id`, `document_number`, posting dates; paging | Posted debits and credits for reconciliation and period analysis. |
| `list_dimensions` | Paging | Discover the dimensions actually configured in the company. |
| `list_dimension_values` | Required `dimension_id`; paging | Values for a configured dimension. |
| `list_general_ledger_entry_dimensions` | Required `general_ledger_entry_id`; paging | Dimension assignments for a posted entry, such as brand or branch where configured. |
| `get_receivables_aging` | Required `customer_id` | Native customer aging, including returned date, periods and currency. |
| `get_payables_aging` | Required `vendor_id` | Native supplier aging, including returned date, periods and currency. |
| `get_trial_balance` | Required `start_date`, `end_date`; paging | Native trial balance rows for the requested period. |
| `get_income_statement` | Required `start_date`, `end_date`; paging | Native income statement rows, including headers and totals. |

Suggested workflows:

1. **Collections:** list customers, then read each customer's native aging. Investigate overdue invoices with `list_sales_invoices(outstanding_only=true, due_before="YYYY-MM-DD")`; retrieve lines to understand the charges. `due_before` is exclusive, and outstanding-only selects `Open` invoices with positive `remainingAmount`. A conflicting status is rejected. These are current balances; filtering posting dates does not reconstruct historical outstanding debt.
2. **Billing corrections:** inspect sales invoice lines and related credit memo headers by customer and credit-memo date. Check status and invoice references before adjusting a revenue analysis. Draft/canceled documents and invoice totals are not automatically recognised revenue.
3. **Business-unit performance:** discover dimensions and their values; retrieve posted entries and each entry's dimension assignments. Use the customer's confirmed account/dimension mappings to analyse revenue, direct labour expense and overhead. The native income statement is company-level; it does not accept a fabricated branch filter. Dimensions are not assumed to identify a brand, site, client or consultant.
4. **Cash and close:** review customer/vendor aging together for receivable/payable visibility, and use the trial balance and income statement for period reconciliation. This is not a payroll funding forecast or bank reconciliation.

Accounting limitations:

- Aging uses BC's report defaults. Read `agedAsOfDate`, `periodLengthFilter`, period labels where supplied, and `currencyCode` from the response; this release does not promise a caller-selected historical aging date. Credit balances remain signed. An empty currency code must be interpreted against the company local currency, not treated as an arbitrary currency.
- Report dates use the API's `dateFilter`, not `postingDate`. Reports remain paged; follow every continuation. Native formatted trial-balance amounts and income-statement `lineType`/`indentation` are preserved. Do not add header/subtotal rows to their detail rows or combine currencies/companies without an agreed conversion and consolidation policy.
- Invoices are billing evidence. Use posted G/L entries for accounting revenue/cost analysis. Payroll, timesheets, placement-level margins, pay/bill rates and statutory payroll obligations need confirmed upstream sources; this integration does not infer them from invoice totals.
- The finance owner must confirm legal entities, account mappings, dimension coverage, credit-control rules and reconciliation to approved BC reports. One brand may span companies or dimensions; no public website can establish that internal setup.

## Inventory and planning semantics

- Item `inventory` is company-wide on-hand stock. It is not warehouse/variant availability or available-to-promise. Locations and variants are reference data only.
- Inspect document status and units before calculating outstanding supply (`quantity - receivedQuantity`) or demand (`quantity - shippedQuantity`). Do not subtract both open sales demand and the reservations backing it.
- Reorder cost is `quantity × item.unitCost` in the company local currency, using the item base unit. It is a recorded-cost budget estimate, not a supplier quote. It excludes freight, duties, discounts, tax and price breaks. Decimal strings preserve calculation precision; no currency rounding is applied.
- `forecast_stock` reads a completed historical window of up to 730 calendar days, follows all ledger pages, and counts only `Sale` entries. Negative Sale quantities represent shipments; positive Sale quantities offset them as returns. Nonnegative net sales divided by all calendar days gives the daily average. The forecast subtracts that daily demand from **current** company-wide inventory for the requested future horizon. Days of cover is null for zero net demand.
- This is an explainable baseline, not a replenishment policy or seasonal forecast. It excludes incoming supply, open orders, reservations, production/assembly demand, transfers, stockout effects and seasonality. An empty history is explicitly counted and does not prove zero demand. Backtest and agree the history window before using recommendations operationally.
- Forecasting fails if history exceeds 10,000 rows, contains duplicate/missing entry IDs or repeats continuation pages. It never silently calculates from truncated history. Shorten the window or use a separate analytical data store for larger workloads. API reads are not a transactional snapshot.

Warehouse/variant stock, reservations, lead times, safety stock, order multiples, supplier price lists and landed costs may require a separately designed AL custom API. This release does not invent endpoints for those fields. A BC partner must validate customer customizations and install any future extension.

## Example workflow

1. `list_companies` → select a company; `list_items` → find an inventory item and read its base unit.
2. Read purchase and sales headers/lines to review dated incoming supply and commitments.
3. `forecast_stock` with a completed historical window to get a transparent starting baseline.
4. `estimate_reorder_cost` with a proposed base-unit quantity; compare it with recent invoice lines and supplier pricing before buying.

## Testing and validation

Use Python 3.13+ with the dependencies in `requirements.txt` and root `requirements-test.txt`.

```bash
pytest microsoft-business-central/ -v
python ../autohive-integrations-tooling/scripts/validate_integration.py microsoft-business-central
python ../autohive-integrations-tooling/scripts/check_code.py --base-ref origin/master microsoft-business-central
```

Read-only live tests require a dedicated sandbox and the four `MICROSOFT_BUSINESS_CENTRAL_*` variables documented in root `.env.example`. The access token must target Business Central. Locally, set it in uncommitted `.env`; platform OAuth handles refresh in deployed workflows. For manual tokens, acquire a fresh token when it expires.

```bash
pytest microsoft-business-central/tests/test_business_central_integration.py -m "integration and not destructive"
```

There are no destructive actions or tests. Live tests skip when credentials are absent; document/forecast tests also skip when their sandbox fixtures are absent. Skipped tests do not demonstrate API compatibility. TeamCity supplies the platform OAuth token automatically; configure its sandbox variables through `tests/teamcity.env` secret markers. Validate API field availability and reconcile stock/cost results in the actual sandbox before release.

## Official references

- [Business Central API v2.0](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/)
- [Entra/Connect app setup](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-develop-connect-apps)
- [Items](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_item), [item ledger entries](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_itemledgerentry)
- [Purchase lines](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_purchaseorderline), [sales lines](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_salesorderline)
- [Sales invoices](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_salesinvoice), [credit memos](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_salescreditmemo_get)
- [General ledger entries](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_generalledgerentry), [entry dimensions](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_dimensionsetline_get)
- [Receivables aging](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_agedaccountsreceivable_get), [payables aging](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_agedaccountspayable_get)
- [Trial balance](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_trialbalance_get), [income statement](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_incomestatement_get)
- [Limits and throttling](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/dynamics-rate-limits)
