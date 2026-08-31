# Windcave Integration for Autohive

Connects Autohive to the [Windcave](https://www.windcave.com/) REST API to retrieve transaction details by ID.

## Description

Windcave is a payment gateway used across New Zealand, Australia, and the Pacific. This integration is **read-only**: it exposes a single action, `get_transaction`, which looks up an existing transaction and returns its authorisation status, settlement date, surcharge, and full raw record.

It does not create, capture, refund, or void payments, and it does not create Hosted Payment Page sessions. Transactions must already exist in your Windcave account — created via the Windcave portal or another client — and are referenced here by `transaction_id`.

No raw card numbers ever pass through Autohive.

## Setup & Authentication

This integration uses **Custom Authentication** with your Windcave REST API credentials.

### Required Authentication Fields

- **`username`**: The REST API username provided by Windcave for your merchant account.
- **`api_key`**: The REST API key provided by Windcave. Combined with the username to form an HTTP Basic Authentication header.

### Setup Steps

1. Contact Windcave (or your onboarding representative) to obtain REST API credentials for your merchant account.
2. Add the Windcave integration in Autohive.
3. Enter the `username` and `api_key` fields.

## Actions

### `get_transaction`
Retrieve a transaction by ID.

**Inputs:** `transaction_id` (required)

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

## API information

- Base URL: `https://uat.windcave.com/api/v1` (Windcave UAT)
- Auth header: `Authorization: Basic <base64(username:api_key)>` (HTTP Basic Authentication)
- Endpoint used: `GET /transactions/{id}`

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Transaction not found` | The `transaction_id` doesn't exist in this Windcave account. |
| `Invalid transaction id` | The `transaction_id` isn't in the format Windcave expects (a well-formed ID looks like 16 hex characters, not a UUID). |
| Missing-credential validation error | Reconnect the integration and provide both the REST API `username` and `api_key`. |
| `401`/authentication errors on every call | `username`/`api_key` are wrong, have been revoked, or belong to a non-UAT environment. |

This integration currently targets Windcave UAT, so it requires UAT REST API credentials. Production credentials for `sec.windcave.com` will not authenticate against this endpoint.

## Testing

### Unit Tests

Run mocked unit tests (no network calls, no credentials needed):

```bash
pytest windcave/tests/test_windcave_unit.py -v
```

### Integration Tests

Integration tests call the real Windcave API and require credentials. Set these in your local `.env` (see the repository root `.env.example`):

```bash
WINDCAVE_USERNAME=
WINDCAVE_API_KEY=
WINDCAVE_TEST_TRANSACTION_ID=
```

`WINDCAVE_TEST_TRANSACTION_ID` is the ID of a transaction that already exists in the account; the success-path test skips without it. This integration is read-only, so no test creates or modifies data and there are no destructive tests.

```bash
pytest windcave/tests/test_windcave_integration.py -m "integration and not destructive"
```

## Notes

- This integration never accepts raw card numbers or CVCs — it only ever reads an existing transaction by ID.
- `settlement_date` and `amount_surcharge` are read directly from Windcave's transaction data (`settlementDate`/`amountSurcharge`) and will be `null` until Windcave settles the transaction (typically the next business day).

### Reconciliation fields: what's available vs. not

For accounts/reconciliation use cases needing Settlement Date, Reference, Amount, Amount Surcharge, and BillingId per transaction:

| Field | Available via this integration? |
|---|---|
| Settlement Date | ✅ `settlement_date` on `get_transaction` |
| Reference | ✅ `merchantReference`, inside the raw `transaction` object |
| Amount | ✅ `amount`, inside the raw `transaction` object |
| Amount Surcharge | ✅ `amount_surcharge` on `get_transaction` |
| BillingId | ❌ Not available. `BillingId`/`DpsBillingId` is part of Windcave's **legacy** PxPay 2.0 / SOAP Web Service token-billing mechanism (`RecurringMode` + `EnableAddBillCard`), a different API generation from the REST API this integration is built on. Getting `BillingId` would require a separate, legacy-API-based integration. |
