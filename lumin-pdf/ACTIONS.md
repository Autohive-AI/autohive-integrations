# Lumin PDF — Action Reference

Base URL: `https://api.luminpdf.com/v1`  
Auth: `X-API-KEY` header on every request.

---

## User & Workspace

### `get_current_user`
Returns profile info for the authenticated API key owner.

- **Inputs:** none
- **Output:** `user` — raw user object from Lumin

---

### `get_workspace`
Returns details about the current workspace (name, plan, settings).

- **Inputs:** none
- **Output:** `workspace` — workspace object

---

### `list_workspace_members`
Lists all members in the workspace with optional pagination.

- **Inputs:**
  - `limit` *(optional)* — members per page
  - `page` *(optional, default: 1)* — page number
- **Output:** `members` — array of member objects

---

## Templates

### `list_templates`
Lists all templates available in the workspace.

- **Inputs:**
  - `limit` *(optional)* — templates per page
  - `page` *(optional, default: 1)* — page number
- **Output:** `templates` — array of template objects
- **Note:** Uses Lumin API version `1.1`

---

### `get_template`
Fetches a single template by its ID.

- **Inputs:**
  - `template_id` *(required)* — the template ID
- **Output:** `template` — template object with fields, roles, etc.
- **Note:** Uses Lumin API version `1.1`

---

## Signature Requests

### `send_signature_request`
Creates and sends a new signature request to one or more signers.

- **Inputs:**
  - `title` *(required)* — name for the request
  - `signers` *(required)* — array of `{ name, email_address }` objects
  - `file_url` *(optional)* — URL of a single PDF to sign
  - `file_urls` *(optional)* — array of URLs if sending multiple documents
  - `message` *(optional)* — message shown to signers
  - `due_date` *(optional)* — ISO 8601 expiry date/time; defaults to 30 days from now
- **Output:** `signature_request` — the created request object (contains `signature_request_id`)

---

### `get_signature_request`
Retrieves the current status and details of a signature request.

- **Inputs:**
  - `signature_request_id` *(required)*
- **Output:** `signature_request` — full request object including signer statuses

---

### `cancel_signature_request`
Cancels a pending signature request. Cannot be undone.

- **Inputs:**
  - `signature_request_id` *(required)*
- **Output:** `canceled: true`

---

### `update_signature_request`
Extends (or changes) the expiry date of a pending request.

- **Inputs:**
  - `signature_request_id` *(required)*
  - `due_date` *(required)* — new expiry as ISO 8601 string (e.g. `"2027-01-01T00:00:00"`)
- **Output:** `signature_request` — updated request object

---

### `generate_signing_link`
Generates an embedded signing URL for a specific signer. Use this to embed the signing experience in your app.

- **Inputs:**
  - `signature_request_id` *(required)*
  - `signer_email` *(required)* — email of the signer to generate the link for
- **Output:** `signing_link` — the URL the signer opens to sign

---

### `send_reminder`
Sends a reminder email to pending signers.

- **Inputs:**
  - `signature_request_id` *(required)*
  - `emails` *(optional)* — array of signer emails to remind; omit to remind all pending signers
- **Output:** `sent: true`

---

### `send_from_template`
Sends a signature request using a saved Lumin template instead of uploading a file.

- **Inputs:**
  - `template_id` *(required)* — ID of the template to use
  - `title` *(required)* — name for the request
  - `signers` *(required)* — array of `{ name, email_address }` objects
  - `message` *(optional)* — message shown to signers
  - `due_date` *(optional)* — ISO 8601 expiry; defaults to 30 days from now
  - `fields` *(optional)* — pre-filled field values
  - `variables` *(optional)* — template variable values
  - `tags` *(optional)* — array of tag strings
- **Output:** `signature_request` — created request object

---

### `download_signed_document`
Gets a download URL for a completed (fully signed) document.

- **Inputs:**
  - `signature_request_id` *(required)*
  - `type` *(optional, default: `"agreement"`)* — document type to download
- **Output:** `file_url` — download URL string; `file` — raw response data
- **Note:** Returns an error if the document hasn't been fully signed yet

---

## Documents

### `upload_document`
Uploads a document to Lumin from a URL, or creates one from a template.

- **Inputs:**
  - `document_name` *(required)* — display name for the document
  - `location` *(optional, default: `"personal"`)* — storage location
  - `file_url` *(optional)* — URL of the PDF to upload
  - `template_id` *(optional)* — create document from a template instead
- **Output:** `document` — created document object
- **Note:** Provide either `file_url` or `template_id`, not both

---

### `generate_document_from_template`
Generates a filled PDF document from a template with custom field values, without sending it for signature.

- **Inputs:**
  - `template_id` *(required)*
  - `document_name` *(required)* — name for the generated document
  - `fields` *(optional)* — field key/value pairs to pre-fill
  - `variables` *(optional)* — template variable values
  - `tags` *(optional)* — array of tag strings
- **Output:** `document` — generated document object

---

## Agreements

### `create_agreement`
Creates an agreement from a Lumin template (non-signature document, e.g. a policy or contract copy).

- **Inputs:**
  - `agreement_name` *(required)*
  - `template_id` *(required)*
  - `fields` *(optional)* — field values to fill in the template
  - `variables` *(optional)* — template variable values
  - `linked_objects` *(optional)* — objects to link to the agreement
- **Output:** `agreement` — created agreement object

---

### `download_agreement`
Gets a download URL for an existing agreement file.

- **Inputs:**
  - `agreement_id` *(required)*
- **Output:** `file_url` — download URL string; `file` — raw response data
