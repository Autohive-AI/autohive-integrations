# Trade Me

Read your Trade Me account details and seller listings. This first version has
five read-only actions. All actions require the `MyTradeMeRead` permission.

Only the sandbox has been verified. Production URLs can be selected, but no
production application or production credentials have been tested. Treat this
version as a sandbox test integration.

| Action | Inputs | Output |
| --- | --- | --- |
| `get_profile` | None | `profile`: member summary with Trade Me field names |
| `list_selling_items` | Optional `filter`, `page`, `rows` | `items`, `total_count`, `page`, `page_size` |
| `list_sold_items` | Optional `filter`, `page`, `rows` | Same page fields; each item is a sale |
| `list_unsold_items` | Optional `filter`, `page`, `rows` | Same page fields |
| `get_selling_listing` | Required positive integer `listing_id` | `listing`: seller editing details |

List actions return one page. The default page is 1. The default page size is 50.
This integration limits `rows` to 100. Increase `page` for more results. Use
`total_count` and the returned items to decide when to stop. Do not treat an
empty page as an API error. Trade Me can return a null `List`; the integration
returns an empty array in that case.

Active listings use `All` by default. Other filters are `ClosingToday`,
`ListingsWithBids`, `ReserveMet`, `ReserveNotMet`, and `UnansweredQuestions`.
Sold and unsold lists use `Last45Days` by default. See `config.json` for their
supported time and status filters. Sold items can contain several sales for
one listing. Keep each sale; do not remove entries with the same `ListingId`.
Dates and provider field names remain in the Trade Me response format.

## Connect your sandbox account

1. Sign in at [Trade Me Sandbox](https://www.tmsandbox.co.nz).
2. Open **My Trade Me > Settings > API Applications**. Register an application.
   Use a name such as `Autohive local testing`. Use a description that explains
   that the app reads your account and seller listings. Under **Application
   type**, select **Client**. This enables the out-of-band PIN flow. The
   **Browser** option requires an HTTPS callback URL and does not match the local
   tool. Leave callback domains blank. Sandbox applications get automatic approval.
3. Keep the **Consumer key** and **Consumer secret** from the application page.
   These are API credentials. Your account password is not used by the code.
4. From this repository root, prepare Python 3.13 and the test tools:

   ```powershell
   uv venv --python 3.13 .venv
   uv pip install --python .venv/Scripts/python.exe -r requirements-test.txt -r trademe/requirements.txt
   ```

   If `.venv` already exists, use it and skip the first command.

5. Run the local authorization tool:

   ```powershell
   .venv/Scripts/python.exe trademe/tests/authorize_sandbox.py
   ```

   Enter the consumer key and secret at the hidden prompts. Open the URL that
   the tool prints. Sign in to your sandbox account. Select **Allow** for
   `MyTradeMeRead`. Enter the seven-digit PIN in the terminal. The tool exchanges
   the PIN for an access token and secret. It saves these four values in the
   repository root `.env`. It preserves other settings in that file.

6. Keep `.env` local. Git ignores it. Do not send credentials in chat or commit
   them. When the file is ready, local tests can use it without more login steps.
7. Optional: create a test listing on the sandbox website. Set
   `TRADEME_TEST_LISTING_ID` in root `.env` to its numeric ID. The listing must
   belong to the account that approved the application. The listing detail
   test skips if this value is missing.
8. Run the read-only live tests:

   ```powershell
   .venv/Scripts/python.exe -m pytest trademe/tests/test_trademe_integration.py -m "integration and not destructive" -v
   ```

The official [OAuth token generator](https://developer.trademe.co.nz/api-overview/authentication)
is an alternative to the local tool. Select **Sandbox** and only
`MyTradeMeRead`. Save the four values in root `.env` with these names:

```dotenv
TRADEME_CONSUMER_KEY=
TRADEME_CONSUMER_SECRET=
TRADEME_ACCESS_TOKEN=
TRADEME_ACCESS_TOKEN_SECRET=
TRADEME_TEST_LISTING_ID=
```

## Autohive connection

The integration uses custom authentication because Trade Me uses OAuth 1.0a.
Supply `consumer_key`, `consumer_secret`, `access_token`, and
`access_token_secret`. Set `environment` to `sandbox` or `production`. If omitted,
the environment is `sandbox`. Host URLs are fixed by the integration.

The Autohive connection form requires manual entry of all four credentials.
Enter `sandbox` in the Environment field if the form does not show a default.
The local `.env` file is not imported into Autohive. This version does not add
platform OAuth 1.0a support or a browser sign-in flow to Autohive.

Requests use OAuth `PLAINTEXT` signatures over HTTPS, as supported by Trade Me.
Each secret is percent-encoded before the signing key is built. The full signing
key is then encoded for the Authorization header.

## Limits and errors

- Trade Me documents a limit of 1,000 authenticated calls per hour per application
  per member. HTTP 429 returns an error. The integration does not loop or retry
  automatically.
- HTTP 401 or 403: check all four credentials, the environment, and the
  `MyTradeMeRead` permission. Sandbox credentials cannot access production.
- HTTP 400: check inputs and listing ownership. Seller listing details require
  the connected account to own the listing.
- Production requires a separate application and Trade Me approval. Marketplace
  API access is limited to in-trade sellers. Confirm your use case with Trade Me
  before production use.
- Listing creation, updates, bidding, and buying are outside this first version.
- `icon.png` is the SDK starter icon. Replace it with an approved Trade Me icon
  before publication.

## Validation

```powershell
.venv/Scripts/python.exe -m pytest trademe/ -v
.venv/Scripts/python.exe ../autohive-integrations-tooling/scripts/validate_integration.py trademe
.venv/Scripts/python.exe ../autohive-integrations-tooling/scripts/check_code.py trademe
```

Unit tests use mocked responses. Live tests use the SDK HTTP client and always
target the sandbox. They skip when credentials are missing. On 26 November 2026,
the profile and three seller list tests passed against the sandbox. The seller
listing detail test skipped because no test listing ID was set.

## Official references

- [Register an application](https://developer.trademe.co.nz/api-overview/registering-an-application)
- [Sandbox environment](https://developer.trademe.co.nz/api-overview/sandbox-environment)
- [Authorization](https://developer.trademe.co.nz/api-overview/authorisation)
- [PIN authorization flow](https://developer.trademe.co.nz/api-overview/authentication/example-plaintext-workflow)
- [Profile](https://developer.trademe.co.nz/api-reference/my-trade-me-methods/retrieve-your-profile-information)
- [Active listings](https://developer.trademe.co.nz/api-reference/my-trade-me-methods/retrieve-your-items-currently-for-sale)
- [Sold items](https://developer.trademe.co.nz/api-reference/my-trade-me-methods/retrieve-your-sold-items)
- [Unsold items](https://developer.trademe.co.nz/api-reference/my-trade-me-methods/retrieve-your-unsold-items)
- [Seller listing details](https://developer.trademe.co.nz/api-reference/selling-methods/retrieve-the-details-of-a-single-listing)
- [Rate limits](https://developer.trademe.co.nz/api-overview/rate-limiting)
