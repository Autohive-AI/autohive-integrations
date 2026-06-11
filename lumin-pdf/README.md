# Lumin PDF Integration for Autohive

Lumin PDF is a cloud-based PDF editing and eSignature platform that enables teams to send, sign, and track documents entirely online. This integration provides 17 actions covering workspace management, document uploading, template discovery, agreement creation, and the full signature request lifecycle.

## Key Features

- Send signature requests directly from a PDF URL or a saved template
- Track signature request status and signer progress
- Generate embedded signing links for in-app signing flows
- Send reminders to pending signers automatically
- Download signed documents, certificates of completion, and merged files
- Upload documents and generate filled PDFs from templates
- Create and download agreements using lumin-type templates
- Manage workspace members and templates

## Setup & Authentication

This integration uses **API Key** authentication.

**To set up:**
1. Sign up for a Lumin account at [luminpdf.com](https://www.luminpdf.com)
2. Navigate to your account's **Developer settings**
3. Generate an **API Key**
4. Enter the API key when connecting via Autohive

## Actions

#### get_current_user
Get information about the currently authenticated Lumin user.

**Inputs:** None

**Outputs:**
- `result` (boolean) — Operation success status
- `user` (object) — Current user details including id, email, and plan info

---

#### get_workspace
Get information about the current workspace.

**Inputs:** None

**Outputs:**
- `result` (boolean) — Operation success status
- `workspace` (object) — Workspace details including id, name, and plan

---

#### list_workspace_members
List all members in the current workspace.

**Inputs:**
- `page` (integer, optional) — Page number for pagination. Must be paired with `limit`.
- `limit` (integer, optional) — Number of results per page. Accepted values: 10, 25, or 50. Other values are rounded to the nearest accepted value. Must be paired with `page`.

**Outputs:**
- `result` (boolean) — Operation success status
- `members` (array) — List of workspace members

---

#### list_templates
List all templates available in the workspace. Returns both `pdf`-type (uploaded PDFs) and `lumin`-type (built in template builder) templates.

**Inputs:**
- `page` (integer, optional) — Page number for pagination. Must be paired with `limit`.
- `limit` (integer, optional) — Number of results per page. Accepted values: 10, 25, or 50. Other values are rounded to the nearest accepted value. Must be paired with `page`.

**Outputs:**
- `result` (boolean) — Operation success status
- `templates` (array) — List of templates with id, name, type, and created_at

---

#### get_template
Get full details of a specific template including its signer roles and field definitions. Use this before calling `send_from_template` to discover the required `signer_role` values.

**Inputs:**
- `template_id` (string, required) — The ID of the template

**Outputs:**
- `result` (boolean) — Operation success status
- `template` (object) — Template details including signer_roles, fields, and variables

---

#### send_signature_request
Send a signature request with one or more PDF documents to specified signers.

**Inputs:**
- `title` (string, required) — Title of the signature request
- `signers` (array, required) — List of signers. Each signer should have `name` and `email_address` (or `email`)
- `file_url` (string, optional) — Single PDF URL to include
- `file_urls` (array, optional) — Multiple PDF URLs to include (use instead of `file_url` for multiple documents)
- `message` (string, optional) — Optional message to include with the request
- `due_date` (string, optional) — Expiry date in ISO 8601 format. Defaults to 30 days from now.

**Outputs:**
- `result` (boolean) — Operation success status
- `signature_request` (object) — Created signature request including id and status

---

#### send_from_template
Send a signature request using a saved lumin-type template. The template must be created in Lumin's template builder (not an uploaded PDF) and have signer roles defined. Use `get_template` first to discover available roles.

**Inputs:**
- `template_id` (string, required) — The ID of the lumin-type template to use
- `title` (string, required) — Title of the signature request
- `signers` (array, required) — List of signers mapped to template roles. Each signer must have `email_address` (or `email`) and `signer_role` matching a role name from the template. All template roles must be covered.
- `due_date` (string, optional) — Expiry date in ISO 8601 format. Defaults to 30 days from now.
- `message` (string, optional) — Optional message to include
- `tags` (object, optional) — Tag values to fill in the template
- `fields` (object, optional) — Field values to pre-fill in the template
- `variables` (object, optional) — Variable values for the template

**Outputs:**
- `result` (boolean) — Operation success status
- `signature_request` (object) — Created signature request details

---

#### get_signature_request
Retrieve details and current status of a specific signature request.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request

**Outputs:**
- `result` (boolean) — Operation success status
- `signature_request` (object) — Signature request details including status and signer progress

---

#### update_signature_request
Extend the expiry date of a pending signature request.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request to update
- `due_date` (string, required) — New expiry date in ISO 8601 format

**Outputs:**
- `result` (boolean) — Operation success status
- `signature_request` (object) — Updated signature request details

---

#### cancel_signature_request
Cancel a pending signature request. Cannot be undone.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request to cancel

**Outputs:**
- `result` (boolean) — Operation success status
- `canceled` (boolean) — Whether the request was successfully canceled

---

#### generate_signing_link
Generate an embedded signing URL for a specific signer in a signature request. Use for in-app or custom signing flows.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request
- `signer_email` (string, required) — Email of the signer to generate a link for

**Outputs:**
- `result` (boolean) — Operation success status
- `signing_link` (string) — The embedded signing URL for the signer

---

#### send_reminder
Send a reminder email to pending signers for a signature request.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request
- `emails` (array, optional) — List of specific signer emails to remind. If omitted, all pending signers (status `NEED_TO_SIGN`) are reminded automatically.

**Outputs:**
- `result` (boolean) — Operation success status
- `sent` (boolean) — Whether the reminder was sent successfully

---

#### download_signed_document
Get a download URL for a completed signed document.

**Inputs:**
- `signature_request_id` (string, required) — The ID of the signature request
- `type` (string, optional) — Document type: `agreement` (signed PDF, default), `coc` (certificate of completion), or `merged` (all in one)

**Outputs:**
- `result` (boolean) — Operation success status
- `file_url` (string) — Download URL for the document
- `file` (object) — Full file response from Lumin

---

#### upload_document
Upload a document to Lumin from a URL or create one from a template.

**Inputs:**
- `document_name` (string, required) — Name for the document
- `file_url` (string, optional) — URL of the file to upload (PDF, DOCX, XLSX, PPTX, PNG, JPEG — max 200MB on paid plans)
- `template_id` (string, optional) — Template ID to create the document from (use instead of `file_url`)
- `location` (string, optional) — Storage location: `personal` (default), `space`, or `workspace`

**Outputs:**
- `result` (boolean) — Operation success status
- `document` (object) — Created document details

---

#### generate_document_from_template
Generate a filled PDF document from a Lumin template with custom field values. Returns a JSON response with a download URL.

**Inputs:**
- `template_id` (string, required) — The ID of the template
- `document_name` (string, required) — Name for the generated document
- `tags` (object, optional) — Tag values to fill in
- `fields` (object, optional) — Field values to fill in
- `variables` (object, optional) — Variable values to fill in

**Outputs:**
- `result` (boolean) — Operation success status
- `document` (object) — Generated document details including download URL

---

#### create_agreement
Create an agreement from a lumin-type template. Requires a template created in Lumin's template builder — does not work with pdf-type templates.

**Inputs:**
- `agreement_name` (string, required) — Name for the agreement
- `template_id` (string, required) — The ID of the lumin-type template to use
- `variables` (object, optional) — Variable values for the template
- `fields` (object, optional) — Field values for the template
- `linked_objects` (array, optional) — Linked objects to associate with the agreement

**Outputs:**
- `result` (boolean) — Operation success status
- `agreement` (object) — Created agreement details including id and preview URL

---

#### download_agreement
Get a download URL for an agreement file.

**Inputs:**
- `agreement_id` (string, required) — The ID of the agreement (from `create_agreement` output)

**Outputs:**
- `result` (boolean) — Operation success status
- `file_url` (string) — Download URL for the agreement file
- `file` (object) — Full file response from Lumin

## Requirements

- `autohive-integrations-sdk`

## API Info

- **Base URL:** `https://api.luminpdf.com/v1`
- **Sandbox URL:** `https://api-sandbox.luminpdf.com/v1`
- **Docs:** [developers.luminpdf.com](https://developers.luminpdf.com/home)
- **API Version header:** `X-Lumin-API-Version: 1.1` (used for template endpoints)
- **Supported file formats:** PDF, DOCX, XLSX, PPTX, DOC, XLS, PNG, JPEG
- **File size limits:** 20 MB (free), 200 MB (paid)

## Rate Limiting

Refer to [Lumin's developer documentation](https://developers.luminpdf.com/home) for current rate limits. The `limit` parameter for list endpoints only accepts values of `10`, `25`, or `50` — other values are automatically rounded to the nearest accepted value.

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Invalid or expired API key | Regenerate your API key in Lumin Developer settings |
| `404 Not Found` | Invalid resource ID | Verify the template, signature request, or agreement ID is correct |
| `400 Bad Request: limit must be an integer` | A non-integer value was passed as `limit` | Ensure `limit` and `page` are integers when provided; omit them to use the API's server-side defaults |
| `400 Bad Request: email_address must not be empty` | Signer missing email in `send_from_template` | Pass `email_address` or `email` for each signer |
| `400 Bad Request: Signer role X is required` | Missing or wrong `signer_role` in `send_from_template` | Use `get_template` to discover required role names and ensure all roles are covered |
| `400 Bad Request` | Missing required fields | Ensure all required inputs are provided |
| `406 Not Acceptable: Invalid accept type` | API received an unsupported Accept header | Handled automatically — the integration sends `Accept: application/json` for download endpoints |
| `422 Cannot convert undefined or null to object` | `send_from_template` called with a pdf-type template | Use a lumin-type template (created in Lumin's template builder) — these have defined signer roles |
| `404 template_not_found` on `/v1/agreements` | `create_agreement` called with a pdf-type or non-existent template ID | Agreements require a lumin-type template; verify the template ID and type |
| `409 signature_request_not_approved` | Downloading before signing is complete | Wait for all signers to complete before downloading |

## Troubleshooting

**`send_from_template` fails with "Signer role X is required"**
Call `get_template` with the template ID first. The response includes `signer_roles` — each entry has a `name` field. Every role must have a corresponding signer entry with a matching `signer_role` value.

**`create_agreement` or `send_from_template` returns 404 template_not_found**
These actions only work with lumin-type templates (built in Lumin's template builder). Uploaded PDFs are `pdf`-type and are not supported. Check the `type` field in `list_templates` output.

**`list_templates` or `list_workspace_members` returns 400 on limit**
Only `10`, `25`, and `50` are valid limit values. The integration rounds other values automatically, but explicit values outside these will be rounded — pass `10`, `25`, or `50` directly to avoid confusion.

**`download_agreement` or `download_signed_document` fails to decode**
These endpoints can return binary PDF data. The integration automatically requests JSON responses via `Accept: application/json` to get a download URL instead of raw bytes. If you see a UTF-8 decode error, ensure you are using version 1.2.0 or later.

**Signing link returns empty**
The signing link is only available after the signature request reaches `NEED_TO_SIGN` status. Wait a few seconds after sending and call `get_signature_request` to confirm status before generating a link.

## Running Integration Tests

Read-only live tests require `LUMIN_PDF_TOKEN` set in environment or `.env`:

```bash
pytest lumin-pdf/tests/test_lumin_pdf_integration.py -m "integration and not destructive"
```

Destructive live tests create, update, delete, and email real Lumin resources. Run only against a test account:

```bash
pytest lumin-pdf/tests/test_lumin_pdf_integration.py -m "integration and destructive"
```

## Version History

- **v1.2.1** — Fixed `list_templates` and `list_workspace_members` always sending `page=1` and `limit=10` defaults, preventing 400 errors when called without pagination params
- **v1.2.0** — Fixed pagination params (page+limit must be sent together), clamped limit to accepted values (10/25/50), fixed `send_from_template` signer normalization to use `signer_role` field, fixed `download_signed_document`/`download_agreement`/`generate_document_from_template` binary decode errors with Accept header, fixed `create_agreement` response double-nesting
- **v1.1.0** — Added `send_from_template`, `update_signature_request`, `upload_document`, `generate_document_from_template`, `create_agreement`, `download_agreement` actions
- **v1.0.0** — Initial release with signature request lifecycle, workspace, and template actions
