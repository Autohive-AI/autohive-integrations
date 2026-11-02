# Procore

Construction project, directory, document folder, RFI, and submittal workflows.

## Developer access and OAuth setup

1. Create a verified-email account at [Procore Developers](https://developers.procore.com/). Create an app and version with **Data Connector → User Level Authentication**. Developer sandbox access is available before production verification.
2. Configure an HTTPS Autohive callback URI, install the app version in the developer sandbox, and authorize a sandbox user.
3. Configure Autohive’s platform OAuth provider named `procore` using the app’s client ID/secret and authorization/token endpoints below. This integration folder does not create or register the provider in the Autohive backend.
4. Match each action’s `environment` to the provider’s configured environment. Use a sandbox-configured provider while testing; switch its credentials and endpoints together for production.
5. For a reusable commercial Autohive connector, use the Marketplace Partner route. Production normally requires organization verification, partnership agreement, and app certification. Self-service sandbox access is not production approval.

| Setting | Production | Developer sandbox |
| --- | --- | --- |
| Authorization | `https://login.procore.com/oauth/authorize` | `https://login-sandbox.procore.com/oauth/authorize` |
| Token | `https://login.procore.com/oauth/token` | `https://login-sandbox.procore.com/oauth/token` |
| REST API | `https://api.procore.com` | `https://sandbox.procore.com` |

Use OAuth2 authorization code with the registered callback and platform-generated state. Store client credentials in platform provider settings. The platform must exchange codes, store access/refresh tokens securely, refresh expired access tokens, and reconnect on revoked authorization. The integration uses `context.fetch()` so the SDK injects the connected bearer token. No arbitrary API hosts are accepted.

User-level access follows the authorized user’s company/project/tool permissions; no speculative scope strings are requested. Every company-scoped action sends `Procore-Company-Id`. Grant only the needed project tools: Portfolio for project changes, Directory for user/vendor reads, RFIs and Submittals for those workflows, and Documents for folder/file reads and folder creation. A company administrator must install the app. Service-account/DMSA configuration is a separate platform concern and is not assumed by this connector.

## Actions

All actions accept `environment` (`production` by default, or `sandbox`). For sandbox connections, explicitly pass `"environment": "sandbox"` on every call, including `list_companies`. Procore can report an expired-token 401 when a valid sandbox token is sent to the production API; refreshing cannot fix an environment mismatch. IDs are positive integers. Lists expose one page at a time when pagination is supported.

| Action | Required inputs | Optional inputs |
| --- | --- | --- |
| `list_companies` | none | `environment` |
| `list_projects` | `company_id` | `environment`, `status`, `name`, `page`, `per_page` |
| `get_project` | `company_id`, `project_id` | `environment` |
| `create_project` | `company_id`, `project` | `environment` |
| `update_project` | `company_id`, `project_id`, `project` | `environment` |
| `list_rfis` | `company_id`, `project_id` | `environment`, `status`, `page`, `per_page` |
| `get_rfi` | `company_id`, `project_id`, `rfi_id` | `environment` |
| `create_rfi` | `company_id`, `project_id`, `rfi` | `environment` |
| `update_rfi` | `company_id`, `project_id`, `rfi_id`, `rfi` | `environment` |
| `recycle_rfi` | `company_id`, `project_id`, `rfi_id` | `environment` |
| `restore_rfi` | `company_id`, `project_id`, `rfi_id` | `environment` |
| `list_submittals` | `company_id`, `project_id` | `environment`, `page`, `per_page` |
| `get_submittal` | `company_id`, `project_id`, `submittal_id` | `environment` |
| `create_submittal` | `company_id`, `project_id`, `submittal` | `environment`, `send_emails` |
| `update_submittal` | `company_id`, `project_id`, `submittal_id`, `submittal` | `environment`, `send_emails` |
| `delete_submittal` | `company_id`, `project_id`, `submittal_id` | `environment` |
| `list_submittal_revisions` | `company_id`, `project_id`, `submittal_id` | `environment` |
| `get_submittal_workflow` | `company_id`, `project_id`, `submittal_id` | `environment` |
| `list_project_users` | `company_id`, `project_id` | `environment`, `page`, `per_page` |
| `get_project_user` | `company_id`, `project_id`, `user_id` | `environment` |
| `list_project_vendors` | `company_id`, `project_id` | `environment`, `page`, `per_page` |
| `get_project_vendor` | `company_id`, `project_id`, `vendor_id` | `environment` |
| `list_locations` | `company_id`, `project_id` | `environment`, `page`, `per_page` |
| `list_submittal_types` | `company_id` | `environment` |
| `list_submittal_statuses` | `company_id` | `environment`, `page`, `per_page` |
| `get_document_root` | `company_id`, `project_id` | `environment` |
| `get_folder` | `company_id`, `project_id`, `folder_id` | `environment` |
| `get_file` | `company_id`, `project_id`, `file_id` | `environment` |
| `create_folder` | `company_id`, `project_id`, `folder` | `environment` |

### Project changes

`create_project` requires `project.name`. `update_project` sends only the supplied project fields. The project object exposes address, description, scheduling dates, project number, value, template/stage/type IDs, office, phone, activity, and timezone fields supported by the documented endpoint.

### RFIs

`create_rfi` requires `rfi.subject`, `rfi.rfi_manager_id`, and `rfi.question.body`. It defaults to `draft=true` to avoid issuing correspondence implicitly; explicitly set `draft=false` to issue. Project-specific fieldsets can require additional values such as assignees and due dates. `update_rfi` sends a nonempty partial RFI object; `recycle_rfi` and `restore_rfi` move records into/out of the recycle bin. The question supports attachment references such as existing Prostore file IDs and upload IDs; raw multipart file uploads are outside this version.

### Submittals

Create/update require `submittal.number` as specified by Procore’s schema. The object includes title, description, revision, type, status ID, manager, contractor, location, dates, package/specification IDs, distribution, custom text fields, and existing Prostore file IDs. Resolve company-specific type/status values with the lookup actions. `send_emails` defaults to false at Procore; set it explicitly when notifications are intended. Workflow data can be read, but multipart approval-workflow editing is outside this version. `delete_submittal` deletes the selected record.

### Documents and directories

`get_document_root` returns the root folder object with child files and folders; `get_folder` navigates a folder, and `get_file` returns metadata including download-related fields when the provider supplies them. `create_folder` requires `folder.name` and can take a parent ID/path. Do not interpret a metadata action as a binary file download. User/vendor/location lookups resolve IDs used in RFIs and submittals.

## Outputs and pagination

Resource actions return `result` containing the provider object. A successful operation with no response body returns an empty result object. Lists return `items`, `next_page`, and `total` (null if no total header is supplied). Follow `next_page` using the same filters, company, project, and environment until null. Links are inspected only for their page number; the integration never follows arbitrary response URLs with bearer credentials. No action silently aggregates an unbounded dataset.

## Errors and limits

HTTP and rate-limit errors propagate through the SDK. A 401 usually requires connection refresh/reconnection; 403 indicates tool, project, or installation access; 422 indicates invalid/project-required fields. Unexpected list/object response shapes fail explicitly. Respect Procore rate-limit headers, back off after 429, and schedule large syncs in bounded pages. Do not automatically retry mutation actions after an ambiguous response, as the provider may already have created the resource.

This integration intentionally covers the workflows above rather than mirroring all Procore endpoints. Financial ledgers, daily logs, drawings, inspections, webhooks, binary uploads/downloads, and administration are not implemented. API versions are selected per documented operation: projects list v1.1, project writes v1.0, RFIs v1.0, submittals v1.1, and directory/document endpoints as listed in the source.

## Testing

Run `hiveup validate procore` and `hiveup test procore`. Every action has a mocked request/response test. Authentication injection and API availability still require live verification. A read-only developer-sandbox smoke test is provided:

```bash
export PROCORE_ACCESS_TOKEN=...
export PROCORE_COMPANY_ID=...
pytest procore/tests/test_procore_integration.py -m integration
```

On 2026-11-02, all 29 actions were exercised successfully against a developer sandbox, including create/update project, draft RFI recycle/restore, folder creation, and submittal create/update/delete. Write tests used disposable test records; the created project was deactivated. A nested document folder supplied the file metadata fixture. The automated live smoke test remains read-only and skips without credentials; live write tests do not run automatically. The 61 mocked unit tests also passed. Production access and production API calls remain unverified.

Build upload packages with `hiveup package procore -o procore.zip`. This bundles the SDK and its dependencies for Lambda; a ZIP containing source files alone fails at startup. The packaged integration was deployed and `list_companies` verified through Lambda against the sandbox.

The icon is sourced from [Procore’s official website](https://www.procore.com/images/apple-touch-icon-180x180.png), centered with padding on a 512×512 canvas.

## API evidence and MCP review

Request fields and methods were checked against the OpenAPI data served by Procore’s official API Explorer on 2026-10-29. The reference URL for each resource is below. A community MCP exists, but Procore’s official reach-in data MCP is planned and not yet available. Community availability does not bypass developer credentials or production approval.

- [Quick start and sandbox](https://developers.procore.com/documentation/content/quick-start-guide)
- [Production verification](https://developers.procore.com/documentation/content/verification-and-production-access)
- [Data connector authentication](https://developers.procore.com/documentation/content/building-data-connection-apps)
- [Official MCP status](https://developers.procore.com/documentation/content/agentic-apis)
- [Community MCP source](https://github.com/TylerIlunga/procore-mcp-server)
- [projects API reference](https://developers.procore.com/reference/rest/projects?version=latest)
- [companies API reference](https://developers.procore.com/reference/rest/companies?version=latest)
- [rfis API reference](https://developers.procore.com/reference/rest/rfis?version=latest)
- [submittals API reference](https://developers.procore.com/reference/rest/submittals?version=latest)
- [project-users API reference](https://developers.procore.com/reference/rest/project-users?version=latest)
- [project-vendors API reference](https://developers.procore.com/reference/rest/project-vendors?version=latest)
- [locations API reference](https://developers.procore.com/reference/rest/locations?version=latest)
- [submittal-types API reference](https://developers.procore.com/reference/rest/submittal-types?version=latest)
- [submittal-statuses API reference](https://developers.procore.com/reference/rest/submittal-statuses?version=latest)
- [project-folders-and-files API reference](https://developers.procore.com/reference/rest/project-folders-and-files?version=latest)
