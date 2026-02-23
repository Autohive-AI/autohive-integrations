# Companies Register Integration for Autohive

Integration with the New Zealand [Companies Register API v2](https://api.business.govt.nz/) for managing registered companies on the NZ Companies Office Register.

## Overview

This integration allows you to retrieve company details, manage company contacts and addresses, and file annual returns for NZ registered companies. It covers the core lifecycle operations most commonly needed when maintaining a company on the Register.

**Important — UUID vs NZBN:**
- **Pre-incorporated companies** (status < 50): use the **UUID** as the identifier
- **Registered companies** (status 50): use the **NZBN** as the identifier for all operations

The API parameter is called `companyUuid` but also accepts the NZBN for registered companies.

## Authentication

This integration uses two credentials:

### 1. Azure API Management Subscription Key
Required for all API calls. Injected server-side via the `COMPANIES_REGISTER_SUBSCRIPTION_KEY` environment variable.
- Obtain from: https://portal.api.business.govt.nz/

### 2. RealMe OAuth 2.0
Required for write operations (updating contacts, filing annual returns).
- Authorization URL: `https://api.business.govt.nz/oauth/authorize`
- Token URL: `https://api.business.govt.nz/oauth/token`

## Environments

| Environment | Base URL |
|---|---|
| Sandbox (default) | `https://api.business.govt.nz/sandbox/companies-office/companies-register/companies/v2` |
| Production | `https://api.business.govt.nz/gateway/companies-office/companies-register/companies/v2` |

To switch to production, update `BASE_URL_V2` in `companies_register.py`.

## Actions

### `get_company_details`
**COMP_03** — Get full details of a company by NZBN (registered) or UUID (pre-incorporated).

Returns company status, contacts, annual return info, and an **ETag**. Store the ETag — it is required when filing an annual return.

| Input | Required | Description |
|---|---|---|
| `companyUuid` | Yes | NZBN for registered companies, UUID for pre-incorporated |
| `ifNoneMatch` | No | Previous ETag for cache optimisation (returns 304 if unchanged) |
| `requestId` | No | Optional UUID for request tracking |

---

### `get_company_contacts`
Get all contacts for a company — addresses, phone numbers and email addresses.

Returns `addressId`, `phoneContactId`, `emailAddressId` values needed to update specific contacts, plus an **ETag** required by `update_company_contact`.

| Input | Required | Description |
|---|---|---|
| `companyUuid` | Yes | NZBN for registered companies, UUID for pre-incorporated |
| `requestId` | No | Optional UUID for request tracking |

---

### `update_company_contact`
**COMP_21** — Update an existing contact (address, phone or email) for a company.

**Rules for address updates:**
- Do **not** include `dpid` — use address lines (`address1`, `address3`) directly
- `effectiveDate` is **required** for all address updates
- `Registered office address` and `Address for service` require `effectiveDate` at least **5 working days** in the future
- `addressPurpose` must match exactly what `get_company_contacts` returned (e.g. `"Address for communication"`)

| Input | Required | Description |
|---|---|---|
| `companyUuid` | Yes | NZBN for registered companies |
| `contactId` | Yes | `addressId`, `phoneContactId` or `emailAddressId` from `get_company_contacts` |
| `etag` | Yes | ETag from `get_company_contacts` |
| `contactType` | Yes | `"address"`, `"phone"`, or `"email"` |
| `physicalOrPostalAddress` | Cond. | Required when `contactType` is `"address"` |
| `phoneContact` | Cond. | Required when `contactType` is `"phone"` |
| `emailAddress` | Cond. | Required when `contactType` is `"email"` |

---

### `add_company_contact`
**COMP_19** — Add a new contact (address, phone or email) to a company.

Each address purpose can only exist **once**. If it already exists use `update_company_contact` instead.

| Input | Required | Description |
|---|---|---|
| `companyUuid` | Yes | NZBN for registered companies |
| `contactType` | Yes | `"address"`, `"phone"`, or `"email"` |
| `physicalOrPostalAddress` | Cond. | Required when `contactType` is `"address"` |
| `phoneContact` | Cond. | Required when `contactType` is `"phone"` |
| `emailAddress` | Cond. | Required when `contactType` is `"email"` |

---

### `search_nz_address`
**COMP_30** — Search the NZ Post address file to find a valid NZ address.

Use this to look up addresses and get a valid `dpid` for `add_company_contact`. Note: do not pass `dpid` to `update_company_contact` — use address lines directly for updates.

| Input | Required | Description |
|---|---|---|
| `find` | Cond. | Address search string e.g. `"1 Queen Street Auckland"` |
| `dpid` | Cond. | NZ Post Delivery Point ID — overrides `find` if provided |
| `limit` | No | Max results (1–100, default 10) |
| `postal` | No | Include postal addresses (PO Boxes). Default false |

---

### `file_annual_return`
**COMP_23** — File an annual return for a registered company.

File only after verifying all company details on the Register are up to date.

**Important:**
- `declaration` must be the exact string: `"I certify that the information contained in this annual return is correct."`
- `companyDetailsConfirmedCorrectAsOfETag` must be the ETag from a recent `get_company_details` call
- `phoneContact` must be a **Mobile** number (used for SMS reminders next year)
- Payment defaults to `directDebit`; use `creditCard` with a `redirectUrl` for online payment

| Input | Required | Description |
|---|---|---|
| `companyUuid` | Yes | Company NZBN |
| `declaration` | Yes | `"I certify that the information contained in this annual return is correct."` |
| `name` | Yes | `{ "firstName": "...", "lastName": "..." }` |
| `emailAddress` | Yes | `{ "emailAddress": "..." }` |
| `designation` | Yes | `"Director"` or `"Authorised Person"` |
| `companyDetailsConfirmedCorrectAsOfETag` | Yes | ETag from `get_company_details` |
| `paymentMethod` | No | `"directDebit"` (default) or `"creditCard"` |
| `redirectUrl` | Cond. | Required when `paymentMethod` is `"creditCard"` |
| `phoneContact` | No | Mobile phone for SMS reminders — `phonePurpose` must be `"Mobile"` |
| `billingReference` | No | Optional billing reference |
| `organisationId` | No | Charge fees to an organisation account instead of the logged-in user |

---

## Common Workflows

### Update a company address
```
1. get_company_contacts(companyUuid=NZBN)
   → note: addressId, exact addressPurpose string, etag

2. update_company_contact(
     companyUuid=NZBN,
     contactId=addressId,
     etag=etag,
     contactType="address",
     physicalOrPostalAddress={
       "addressId": addressId,
       "addressType": "Physical",
       "addressPurpose": "<exact purpose from step 1>",
       "address1": "1 Queen Street",
       "address3": "Auckland",
       "postCode": "1010",
       "countryCode": "NZ",
       "effectiveDate": "2026-03-05T00:00:00Z"  // +7 days minimum
     }
   )
```

### File an annual return
```
1. get_company_details(companyUuid=NZBN)
   → note: etag

2. file_annual_return(
     companyUuid=NZBN,
     declaration="I certify that the information contained in this annual return is correct.",
     name={"firstName": "Jane", "lastName": "Smith"},
     emailAddress={"emailAddress": "jane@company.co.nz"},
     designation="Director",
     companyDetailsConfirmedCorrectAsOfETag=etag,
     paymentMethod="directDebit"
   )
```

## Testing

```bash
cd companies-register/tests
python test_companies_register.py
```

Update `SUBSCRIPTION_KEY`, `ACCESS_TOKEN`, and `TEST_NZBN` at the top of the test file before running.

**Sandbox test card:** `4111 1111 1111 1111` (any expiry/CVC)

## API Reference

- [Companies Register API Portal](https://portal.api.business.govt.nz/)
- API Version: v2
