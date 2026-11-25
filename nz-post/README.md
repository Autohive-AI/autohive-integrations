# NZ Post

Search and check New Zealand addresses using ParcelAddress and NZPost.AddressChecker.
Users do not need a NZ Post account, API key, or OAuth connection. Autohive
authenticates with its own approved NZ Post application using OAuth client credentials.

## Actions

| Action | Inputs | Output |
| --- | --- | --- |
| `search_addresses` | `query` (at least four trimmed characters), optional `count` (1–10, default 10) | `addresses` containing `full_address`, `address_id`, and optionally `dpid` |
| `get_address` | Numeric `address_id` from search | `address` containing postcode, suburb, city, rural-delivery status, coordinates and other available NZ Post fields |
| `check_address` | Required `address_line_1`, optional `address_line_2` through `address_line_5`, optional `count` (1-10, default 10) | Candidate `addresses` with `DPID`, `FullAddress`, `MatchScore`, `Deliverable`, and other provider fields |
| `get_postal_address_details` | Numeric `dpid` | Postal `details` including formatted address lines, postcode, coordinates, delivery flags and rural-delivery data when present |
| `search_partial_addresses` | `query`, optional `count` (1-10, default 10) | Partial-address suggestions containing `UniqueId` and `FullPartial` |

Examples:

```json
{"query": "151 Victoria", "count": 5}
```

```json
{"address_id": "949793"}
```

AddressChecker examples:

```json
{"address_line_1": "8 Waterloo Quay", "address_line_2": "Pipitea", "address_line_3": "Wellington", "count": 5}
```

```json
{"dpid": "109570"}
```

```json
{"query": "willis", "count": 5}
```

`check_address` returns candidates without selecting one or applying a score
threshold. A high match score does not establish that an address is correct.
Keep `Deliverable` separate from matching: `N` means NZ Post does not report
mail delivery to that address. A rural postal address with `Deliverable=N` is
not valid for mail delivery. Optional lines containing only spaces are omitted.

`address_id`, `DPID`, and partial-address `UniqueId` identify different resources.
Pass a selected DPID as a string to `get_postal_address_details`. A partial-address
suggestion is not a confirmed complete delivery address. The details action
preserves NZ Post's object or array response and nullable postal fields.

Example identifiers come from NZ Post's documentation and are not guaranteed to be
valid live records. The live test retrieves a current address ID from search results.

Responses preserve NZ Post's `success`, `message_id`, optional warnings and data.
An empty address list is a successful search with no matches.
Partial-result warnings (`200001`, `200002`) are retained when NZ Post reports success.
HTTP errors and unsuccessful application responses return an SDK `ActionError`.

## Shared application credentials

There is deliberately no `auth` block in `config.json`: no user connection is
required. This does **not** make the upstream APIs public. Credentials must be
injected by the Autohive deployment environment and are never accepted as action
inputs or stored in this repository.

| Environment variable | Purpose |
| --- | --- |
| `NZPOST_CLIENT_ID` | Required: Autohive's approved NZ Post application client ID |
| `NZPOST_CLIENT_SECRET` | Required: corresponding application secret |
| `NZPOST_ENVIRONMENT` | Optional: `production` (default) or `uat`; selects the NZ Post API host |

Tokens are obtained from `https://oauth.nzpost.co.nz/as/token.oauth2` using a
form-encoded client-credentials request. Tokens are cached in process until
60 seconds before expiry. Credential rotation or an environment change invalidates
reuse. A rejected token triggers one renewal and one retry of the lookup.
No address data is cached. No credentials are returned in action output.
Missing deployment credentials produce an administrator-facing setup error.

## Steps requiring an Autohive administrator / NZ Post

1. Sign in to NZ Post's developer portal and register **Autohive** as an application
   using **Client Credentials Grant**. Describe the intended service for multiple
   Autohive customers and obtain NZ Post's approval for that use.
2. Request access to **ParcelAddress** and **NZPost.AddressChecker** for that
   application. Each API needs its own approved access request.
   Request UAT access from NZ Post API support if needed and follow their supplied
   environment credential instructions. Do not assume production approval includes UAT.
3. Place the issued client ID and secret into Autohive's server-side secret/configuration
   system and arrange injection as `NZPOST_CLIENT_ID` and `NZPOST_CLIENT_SECRET` in
   the integration runtime. This repository does not configure platform secret injection.
   Keep the secret out of code, commits, action inputs, and chat.
4. Run the read-only live tests below for both APIs.
   Complete NZ Post's go-live checklist and obtain production access before enabling
   the integration for users. Review the shared application's approved rate tier.
5. Deploy the integration through Autohive's normal integration deployment process
   and enable it after live verification. No end-user NZ Post connection is required.

All five actions passed live production verification through the real SDK HTTP
client. The three live tests cover ParcelAddress search/details, AddressChecker
matching/postal details, and partial-address search. Local credentials are stored
in the ignored root `.env` with `NZPOST_ENVIRONMENT=production`; deployment still
requires secure runtime credential injection. UAT access was not established.
Approval for the intended multi-customer use remains a release prerequisite.

## Limits and scope

- NZ Post documents a limit of 15 calls per second for these lookup endpoints.
  The application shares its access tier across users. HTTP 429 errors return retry
  guidance; this integration does not implement a distributed platform-wide limiter.
- ParcelAddress search returns at most ten suggestions; the API provides no pagination.
  AddressChecker actions also request at most ten matches per call in this integration.
  It supports New Zealand addresses only. NZ Post ignores search punctuation other
  than forward slashes.
- Allow manual address entry in calling workflows if NZ Post is unavailable.
- NZ Post restricts ParcelAddress to capturing addresses for its shipping labels.
  Confirm approval before offering general address lookup to Autohive customers.
- This release does not create labels, book pickups, create webhook subscriptions,
  or retrieve shipping rates. The current domestic ShippingOptions API requires a
  customer account number plus an auth code or site code. Shipping actions need
  separate customer account authorisation and are outside this account-free lookup release.

## Tests and validation

Install Python 3.13+, the repository test requirements, and this integration's requirements.
Run from the repository root:

```sh
pytest nz-post/ -v
python ../autohive-integrations-tooling/scripts/validate_integration.py nz-post
python ../autohive-integrations-tooling/scripts/check_code.py nz-post
```

For live tests, set `NZPOST_CLIENT_ID`, `NZPOST_CLIENT_SECRET`, optional
`NZPOST_ENVIRONMENT` in a local root `.env`
(see `.env.example`). Run explicitly:

```sh
pytest nz-post/tests/test_nz_post_integration.py -m integration -v
```

Missing credentials skip the live tests. They use the real SDK HTTP client and
make address lookup calls only. They cover ParcelAddress search/details,
AddressChecker matching/postal details, and partial-address search.

## Official references

- [Apply for API access](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/getting_started/minor/1.0/pages/Applying%20for%20API%20Access/)
- [Authentication](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/parceladdress-api/minor/1.0/pages/Authentication/)
- [Search addresses](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/parceladdress-api/minor/1.0/pages/Search%20for%20Address/)
- [Address details](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/parceladdress-api/minor/1.0/pages/Get%20Address%20Detail%20-%20addressid/)
- [Environments and testing](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/parceladdress-api/minor/1.0/pages/Environments%20and%20Testing/)
- [ParcelAddress use restrictions](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/parceladdress-api/minor/1.0/pages/ParcelAddress%20Overview/)
- [Find address matches](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/nzpost.addresschecker/minor/1.0/pages/Find%20Addresses/)
- [Postal address details](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/nzpost.addresschecker/minor/1.0/pages/Address%20Details/)
- [Partial address suggestions](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/nzpost.addresschecker/minor/1.0/pages/Suggest%20Partial%20Addresses/)
- [AddressChecker](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/nzpost.addresschecker/)
- [Domestic shipping rates and account authentication](https://anypoint.mulesoft.com/exchange/portals/nz-post-group/b8271f09-2ad8-4e1c-b6b1-322c5727d148/shippingoptions-api/minor/1.0/pages/bcp-l3l/Domestic/)

Icon source: [NZ Post website logo](https://www.nzpost.co.nz/themes/custom/nzpost_kahuku/images/logos/nzpost-logo-k.svg), rendered onto a 512×512 white canvas.
