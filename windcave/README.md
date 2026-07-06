# Windcave Integration for Autohive

Connects Autohive to the [Windcave](https://www.windcave.com/) REST API to create hosted payment sessions and manage transactions — direct charges, completions, refunds, and voids.

## Description

Windcave is a payment gateway used across New Zealand, Australia, and the Pacific. This integration covers the two core Windcave REST API workflows:

- **Hosted Payment Page (HPP) sessions** — create a session and redirect a customer to Windcave to securely enter their card details, then query the session for the outcome.
- **Merchant-initiated transactions** — run direct purchases, authorisations, completions, refunds, and voids against a previously stored card token, without handling raw card data yourself.

No raw card numbers ever pass through Autohive — sessions collect card details on Windcave's hosted page, and direct transactions use a `card_id` token issued by a prior session created with `store_card` enabled.

## Setup & Authentication

This integration uses **Custom Authentication** with your Windcave REST API credentials.

### Required Authentication Fields

- **`username`**: The REST API username provided by Windcave for your merchant account.
- **`api_key`**: The REST API key provided by Windcave. Combined with the username to form an HTTP Basic Authentication header.
- **`use_test_environment`** (optional): Enable to send requests to Windcave's UAT environment instead of production. UAT requires separate credentials issued by Windcave.

### Setup Steps

1. Contact Windcave (or your onboarding representative) to obtain REST API credentials for your merchant account — a username and API key for production, and optionally a separate set for UAT.
2. Add the Windcave integration in Autohive.
3. Enter the `username` and `api_key` fields.
4. Toggle `use_test_environment` on if you're configuring against Windcave's UAT environment.

## Actions

### `create_session`
Create a Hosted Payment Page (HPP) session for a purchase, authorisation, or card validation.

**Inputs:**
- `type` (optional): `purchase`, `auth`, or `validate` (default: `purchase`)
- `amount` (required for `purchase`/`auth`): Transaction amount, e.g. `19.99`
- `currency` (required): 3-letter ISO 4217 currency code, e.g. `NZD`
- `merchant_reference` (required): Your reference for this transaction
- `methods` (optional): Payment methods to allow, e.g. `["card"]`
- `store_card` (optional): Store the card as a reusable token
- `language` (optional): Language code for the hosted page, e.g. `en`
- `approved_callback_url`, `declined_callback_url`, `cancelled_callback_url` (optional): Browser redirect URLs
- `notification_url` (optional): Server-to-server result notification URL
- `amount_surcharge` (optional): Surcharge amount to add on top of `amount`, e.g. a card processing fee passed on to the customer

**Outputs:**
- `session_id`, `state`, `hpp_url` (redirect the customer here), `session` (raw object), `result`

### `get_session`
Retrieve a session and the outcome of any transaction attempts made during it.

**Inputs:** `session_id` (required)

**Outputs:** `session_id`, `state`, `authorised`, `settlement_date`, `amount_surcharge`, `transactions`, `session` (raw object), `result`

### `create_transaction`
Run a direct purchase, authorisation, or validation against a stored card token — no hosted page redirect.

**Inputs:**
- `type` (optional): `purchase`, `auth`, or `validate` (default: `purchase`)
- `amount` (required for `purchase`/`auth`)
- `amount_surcharge` (optional): Surcharge amount to add on top of `amount`
- `currency` (required), `merchant_reference` (required)
- `card_id` (required): Stored card token from a prior session created with `store_card: true`

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

### `get_transaction`
Retrieve a transaction by ID.

**Inputs:** `transaction_id` (required)

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

### `complete_transaction`
Capture a prior `auth` transaction.

**Inputs:** `transaction_id` (required), `amount` (optional — defaults to the full authorised amount), `amount_surcharge` (optional), `merchant_reference` (optional)

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

### `refund_transaction`
Refund a prior purchase or completed transaction, in full or in part, by referencing its transaction ID.

**Inputs:** `transaction_id` (required), `amount` (optional — defaults to a full refund), `amount_surcharge` (optional), `merchant_reference` (optional)

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

### `void_transaction`
Void a prior transaction before it settles.

**Inputs:** `transaction_id` (required), `merchant_reference` (optional)

**Outputs:** `transaction_id`, `authorised`, `settlement_date`, `amount_surcharge`, `transaction` (raw object), `result`

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
WINDCAVE_TEST_CARD_ID=
```

`WINDCAVE_USERNAME` and `WINDCAVE_API_KEY` should be UAT credentials. `WINDCAVE_TEST_CARD_ID` is an optional stored card token (obtained by completing a `store_card` session in the UAT environment) used to exercise `create_transaction`.

Run the safe, read-only tests:

```bash
pytest windcave/tests/test_windcave_integration.py -m "integration and not destructive"
```

Run destructive tests (creates real sessions/transactions in the UAT environment) only when you've confirmed it's safe to do so:

```bash
pytest windcave/tests/test_windcave_integration.py -m "integration and destructive"
```

## Notes

- All amounts are decimal values (e.g. `19.99`), formatted internally as the string Windcave's API expects.
- This integration never accepts raw card numbers or CVCs — card data is only ever entered on Windcave's own Hosted Payment Page, or referenced via a `card_id` token issued by Windcave.
- `settlement_date` and `amount_surcharge` are read directly from Windcave's transaction data (`settlementDate`/`amountSurcharge`) and will be `null` until Windcave settles the transaction (typically the next business day).

### Reconciliation fields: what's available vs. not

For accounts/reconciliation use cases needing Settlement Date, Reference, Amount, Amount Surcharge, and BillingId per transaction:

| Field | Available via this integration? |
|---|---|
| Settlement Date | ✅ `settlement_date` on `get_session`/`get_transaction`/etc. |
| Reference | ✅ `merchantReference`, inside the raw `transaction`/`session` object |
| Amount | ✅ `amount`, inside the raw `transaction`/`session` object |
| Amount Surcharge | ✅ `amount_surcharge` on `get_session`/`get_transaction`/etc. |
| BillingId | ❌ Not available. `BillingId`/`DpsBillingId` is part of Windcave's **legacy** PxPay 2.0 / SOAP Web Service token-billing mechanism (`RecurringMode` + `EnableAddBillCard`), a different API generation from the REST API this integration is built on. Getting `BillingId` would require a separate, legacy-API-based integration. |
