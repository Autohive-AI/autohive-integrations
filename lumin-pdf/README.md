# Lumin PDF

Lumin PDF is a cloud-based PDF editing and eSignature platform that enables teams to send, sign, and track documents entirely online. This integration provides 17 actions covering workspace management, document uploading, template discovery, agreement creation, and the full signature request lifecycle.

## Authentication

This integration uses API Key authentication.

**To set up:**
1. Sign up for a Lumin account at [luminpdf.com](https://www.luminpdf.com)
2. Navigate to your account's **Developer settings**
3. Generate an **API Key**
4. Enter the API key when connecting via Autohive

## Actions

| Action | Description | Key Inputs | Key Outputs |
|--------|-------------|------------|-------------|
| `get_current_user` | Get the authenticated user's info | — | `user` |
| `get_workspace` | Get details of the current workspace | — | `workspace` |
| `list_workspace_members` | List all members in the workspace | `page`, `limit` | `members` |
| `list_templates` | List all templates in the workspace | `page`, `limit` | `templates` |
| `get_template` | Get details of a specific template | `template_id` | `template` |
| `upload_document` | Upload a document to Lumin from a URL or template | `document_name`, `file_url` or `template_id`, `location` | `document` |
| `generate_document_from_template` | Generate a filled document from a template | `template_id`, `document_name`, `fields`, `tags`, `variables` | `document` |
| `send_signature_request` | Send a signature request to one or more signers | `title`, `file_url`, `signers` | `signature_request` |
| `send_from_template` | Send a signature request using a saved template | `template_id`, `title`, `signers` | `signature_request` |
| `get_signature_request` | Get the status and details of a signature request | `signature_request_id` | `signature_request` |
| `update_signature_request` | Extend the expiry date of a pending signature request | `signature_request_id`, `due_date` | `signature_request` |
| `generate_signing_link` | Generate an embedded signing URL for a signer | `signature_request_id`, `signer_email` | `signing_link` |
| `send_reminder` | Send a reminder email to pending signers | `signature_request_id`, `emails` | `sent` |
| `download_signed_document` | Download the completed signed PDF, certificate of completion, or merged document | `signature_request_id`, `type` | `file_url`, `file` |
| `cancel_signature_request` | Cancel a pending signature request | `signature_request_id` | `canceled` |
| `create_agreement` | Create an agreement from a template | `agreement_name`, `template_id`, `variables`, `fields` | `agreement` |
| `download_agreement` | Get a download URL for an agreement file | `agreement_id` | `file_url`, `file` |

## API Info

- **Base URL:** `https://api.luminpdf.com/v1`
- **Sandbox URL:** `https://api-sandbox.luminpdf.com/v1`
- **Docs:** [developers.luminpdf.com](https://developers.luminpdf.com/home)
- **Supported file formats:** PDF, DOCX, XLSX, PPTX, DOC, XLS, PNG, JPEG
- **File size limits:** 20 MB (free), 200 MB (paid)
- **Rate limits:** Refer to Lumin's developer documentation for current limits

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Invalid or expired API key | Regenerate your API key in Lumin Developer settings |
| `404 Not Found` | Invalid resource ID | Verify the template, signature request, or agreement ID is correct |
| `400 Bad Request` | Missing required fields | Ensure all required inputs are provided |
| `409 signature_request_not_approved` | Trying to download before signing is complete | Wait for all signers to complete before downloading |
