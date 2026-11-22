# Microsoft Dynamics 365 Business Central

Read-only Business Central Online integration for inventory visibility, purchase-cost investigation and baseline stock planning. Uses standard REST API v2.0 and platform-managed OAuth. No purchase orders, postings or payments are created.

## Connection setup

An Autohive administrator must configure the **Microsoft Business Central** OAuth provider before this integration can be connected. Declaring it in `config.json` does not create a provider or an Entra registration.

`oauth-provider.example.json` is a placeholder-only example of the provider's **details** JSON for a provider named `Microsoft Business Central` with auth type `PlatformOauth2`. Replace the client ID and secure-parameter name through the platform's reviewed provider configuration process. It is not an automatic import or a deployment script.

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
- [Limits and throttling](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/dynamics-rate-limits)
