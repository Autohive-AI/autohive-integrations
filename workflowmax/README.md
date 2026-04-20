# WorkflowMax Integration for Autohive

WorkflowMax (by Xero) is a cloud-based job management and project tracking platform built for professional services businesses — agencies, consultancies, and trades. It centralises client management, job tracking, time logging, invoicing, quoting, and purchasing in a single system.

## Key Features

- Full client and contact management (create, update, list, retrieve)
- Job lifecycle management with status tracking and date control
- Timesheet logging against jobs and tasks with staff attribution
- Invoice and quote creation and retrieval with date/status filtering
- Task management with estimated time and completion tracking
- Staff directory access for team lookups
- Lead tracking for sales pipeline management
- Cost and purchase order management for job financials

## Setup & Authentication

WorkflowMax uses **OAuth 2.0** via the Xero/WorkflowMax identity platform (platform auth).

**Required scopes:** `openid`, `profile`, `email`, `workflowmax`, `offline_access`

**Steps:**

1. Go to [developer.workflowmax.com](https://developer.workflowmax.com) and sign in with your WorkflowMax account.
2. Create a new OAuth 2.0 app and set the redirect URI to your Autohive callback URL.
3. Note your **Client ID** and **Client Secret** — these are configured in Autohive, not passed directly.
4. In Autohive, connect the WorkflowMax integration. You'll be redirected to WorkflowMax to grant access.
5. Access tokens expire after 30 minutes and are automatically refreshed using the `offline_access` refresh token (valid 60 days).

---

## Actions

### Clients

#### `list_clients`

List all clients in the WorkflowMax organisation with optional pagination.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number for pagination (1-based). Omit to retrieve the first page. |
| `page_size` | integer | No | Number of client records to return per page. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the request succeeded, `false` on error. |
| `clients` | array | List of client objects returned by the API. |
| `error` | string | Error message if `result` is `false`. |

---

#### `get_client`

Retrieve a single client record by their WorkflowMax UUID.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `uuid` | string | Yes | The UUID of the client to retrieve. Obtain from `list_clients`. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the client was found and returned. |
| `client` | object | Full client record including name, contact info, and custom fields. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_client`

Create a new client record in WorkflowMax.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The display name of the client. |
| `email` | string | No | Primary email address for the client. |
| `phone` | string | No | Primary phone number for the client. |
| `address` | string | No | Street address line for the client. |
| `city` | string | No | City where the client is located. |
| `region` | string | No | Region, state, or province for the client. |
| `country` | string | No | Country where the client is located. |
| `postal_code` | string | No | Postal or ZIP code for the client. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the client was created successfully. |
| `client` | object | The newly created client record including its assigned UUID. |
| `error` | string | Error message if `result` is `false`. |

---

#### `update_client`

Update fields on an existing client record.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `uuid` | string | Yes | UUID of the client to update. |
| `name` | string | No | Updated display name for the client. |
| `email` | string | No | Updated primary email address. |
| `phone` | string | No | Updated phone number. |
| `address` | string | No | Updated street address. |
| `city` | string | No | Updated city. |
| `region` | string | No | Updated region or state. |
| `country` | string | No | Updated country. |
| `postal_code` | string | No | Updated postal or ZIP code. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the client was updated. |
| `client` | object | The updated client record. |
| `error` | string | Error message if `result` is `false`. |

---

### Client Contacts

#### `list_client_contacts`

List all contacts associated with a specific client.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `client_uuid` | string | Yes | UUID of the client whose contacts to retrieve. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if contacts were retrieved successfully. |
| `contacts` | array | List of contact objects for the specified client. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_client_contact`

Add a new contact person to an existing client.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `client_uuid` | string | Yes | UUID of the client to add the contact to. |
| `name` | string | Yes | Full name of the contact person. |
| `email` | string | No | Email address of the contact. |
| `phone` | string | No | Phone number of the contact. |
| `mobile` | string | No | Mobile/cell number of the contact. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the contact was created. |
| `contact` | object | The newly created contact record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

### Jobs

#### `list_jobs`

List all jobs in the organisation with optional pagination and date filtering.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number for pagination (1-based). |
| `page_size` | integer | No | Number of jobs to return per page. |
| `last_modified` | string | No | ISO 8601 timestamp — only return jobs modified after this date/time. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if jobs were retrieved successfully. |
| `jobs` | array | List of job summary objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `get_job`

Retrieve the full details of a single job by UUID or job number.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identifier` | string | Yes | The UUID or alphanumeric job number of the job to retrieve. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the job was found. |
| `job` | object | Full job record including tasks, costs, status, and dates. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_job`

Create a new job and associate it with a client.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Display name for the job. |
| `client_uuid` | string | Yes | UUID of the client this job belongs to. |
| `description` | string | No | Detailed description of the job scope. |
| `start_date` | string | No | Planned start date in ISO 8601 format (e.g. `2025-01-15`). |
| `due_date` | string | No | Deadline for job completion in ISO 8601 format. |
| `category_uuid` | string | No | UUID of the job category to classify this job. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the job was created. |
| `job` | object | The newly created job record including its assigned UUID and job number. |
| `error` | string | Error message if `result` is `false`. |

---

#### `update_job`

Update fields on an existing job, including its status.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identifier` | string | Yes | UUID or job number of the job to update. |
| `name` | string | No | Updated job name. |
| `description` | string | No | Updated job description. |
| `start_date` | string | No | Updated start date in ISO 8601 format. |
| `due_date` | string | No | Updated due date in ISO 8601 format. |
| `state` | string | No | Updated job status. Common values: `Active`, `Completed`, `Cancelled`. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the job was updated. |
| `job` | object | The updated job record. |
| `error` | string | Error message if `result` is `false`. |

---

### Timesheets

#### `list_timesheets`

List timesheet entries with optional filtering by date range, staff member, or job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | No | Start of the date range in ISO 8601 format. |
| `to_date` | string | No | End of the date range in ISO 8601 format. |
| `staff_uuid` | string | No | Filter to only return timesheets for this staff member UUID. |
| `job_uuid` | string | No | Filter to only return timesheets logged against this job UUID. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if timesheets were retrieved. |
| `timesheets` | array | List of timesheet entry objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `add_timesheet`

Log a time entry for a staff member against a specific job and task.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_uuid` | string | Yes | UUID of the job to log time against. |
| `task_uuid` | string | Yes | UUID of the task within the job to log time against. |
| `staff_uuid` | string | Yes | UUID of the staff member who performed the work. |
| `minutes` | integer | Yes | Duration of the time entry in minutes (e.g. `90` for 1.5 hours). |
| `date` | string | Yes | Date the work was performed in ISO 8601 format. |
| `note` | string | No | Optional description or note for the time entry. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the time entry was created. |
| `timesheet` | object | The created timesheet record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

### Invoices

#### `list_invoices`

List invoices with optional filtering by date range, client, or status.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | No | Start of the invoice date range in ISO 8601 format. |
| `to_date` | string | No | End of the invoice date range in ISO 8601 format. |
| `client_uuid` | string | No | Filter to invoices for this client UUID only. |
| `status` | string | No | Filter by invoice status. Common values: `Draft`, `Approved`, `Paid`. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if invoices were retrieved. |
| `invoices` | array | List of invoice summary objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `get_invoice`

Retrieve the full details of a single invoice by UUID.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `uuid` | string | Yes | UUID of the invoice to retrieve. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the invoice was found. |
| `invoice` | object | Full invoice record including line items, totals, tax, and payment status. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_invoice`

Create a new invoice for a client, optionally linked to a job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `client_uuid` | string | Yes | UUID of the client being invoiced. |
| `date` | string | Yes | Invoice date in ISO 8601 format. |
| `amount` | number | Yes | Invoice amount excluding tax. |
| `job_uuid` | string | No | UUID of the job this invoice relates to. |
| `due_date` | string | No | Payment due date in ISO 8601 format. |
| `description` | string | No | Description or reference text for the invoice. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the invoice was created. |
| `invoice` | object | The created invoice record including its UUID and invoice number. |
| `error` | string | Error message if `result` is `false`. |

---

### Quotes

#### `list_quotes`

List quotes with optional filtering by date range or client.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | No | Start of the quote date range in ISO 8601 format. |
| `to_date` | string | No | End of the quote date range in ISO 8601 format. |
| `client_uuid` | string | No | Filter to quotes for this client UUID only. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if quotes were retrieved. |
| `quotes` | array | List of quote objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_quote`

Create a new quote linked to a job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_uuid` | string | Yes | UUID of the job this quote is for. |
| `date` | string | Yes | Quote issue date in ISO 8601 format. |
| `amount` | number | Yes | Quoted amount excluding tax. |
| `expiry_date` | string | No | Date after which the quote expires, in ISO 8601 format. |
| `description` | string | No | Description or scope summary for the quote. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the quote was created. |
| `quote` | object | The created quote record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

### Tasks

#### `list_tasks`

List tasks, optionally scoped to a specific job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_uuid` | string | No | UUID of the job to list tasks for. Omit to retrieve tasks across all jobs. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if tasks were retrieved. |
| `tasks` | array | List of task objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_task`

Create a new task within a job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Display name for the task. |
| `job_uuid` | string | Yes | UUID of the job this task belongs to. |
| `description` | string | No | Detailed description of the task scope. |
| `estimated_minutes` | integer | No | Estimated duration for the task in minutes. |
| `start_date` | string | No | Planned start date in ISO 8601 format. |
| `due_date` | string | No | Task deadline in ISO 8601 format. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the task was created. |
| `task` | object | The created task record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

#### `update_task`

Update an existing task's details or mark it as complete.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `uuid` | string | Yes | UUID of the task to update. |
| `name` | string | No | Updated task name. |
| `description` | string | No | Updated task description. |
| `estimated_minutes` | integer | No | Updated estimated time in minutes. |
| `due_date` | string | No | Updated due date in ISO 8601 format. |
| `completed` | boolean | No | Set to `true` to mark the task as completed. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the task was updated. |
| `task` | object | The updated task record. |
| `error` | string | Error message if `result` is `false`. |

---

### Staff

#### `list_staff`

List all staff members in the WorkflowMax organisation.

**Inputs:** None required.

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if staff were retrieved. |
| `staff` | array | List of staff member objects including names, roles, and UUIDs. |
| `error` | string | Error message if `result` is `false`. |

---

#### `get_staff`

Retrieve the profile of a single staff member by UUID.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `uuid` | string | Yes | UUID of the staff member to retrieve. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the staff member was found. |
| `staff_member` | object | Full staff profile including contact info, role, and employment details. |
| `error` | string | Error message if `result` is `false`. |

---

### Leads

#### `list_leads`

List all leads in the sales pipeline with optional pagination.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number for pagination (1-based). |
| `page_size` | integer | No | Number of leads to return per page. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if leads were retrieved. |
| `leads` | array | List of lead objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_lead`

Create a new lead entry in the WorkflowMax sales pipeline.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Name or title of the lead opportunity. |
| `client_uuid` | string | No | UUID of an existing client to associate with this lead. |
| `contact_name` | string | No | Name of the primary contact for the lead. |
| `email` | string | No | Email address for the lead contact. |
| `phone` | string | No | Phone number for the lead contact. |
| `description` | string | No | Description of the lead opportunity or requirements. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the lead was created. |
| `lead` | object | The created lead record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

### Costs

#### `list_costs`

List cost entries, optionally filtered to a specific job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_uuid` | string | No | UUID of a job to filter cost entries by. Omit to list all costs. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if costs were retrieved. |
| `costs` | array | List of cost entry objects with pricing and supplier details. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_cost`

Add a cost entry to a job, tracking purchases or expenses.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_uuid` | string | Yes | UUID of the job to assign this cost to. |
| `description` | string | Yes | Description of the cost or expense. |
| `unit_cost` | number | Yes | Cost price per unit (what you paid). |
| `quantity` | number | No | Number of units for this cost entry. Defaults to 1 if omitted. |
| `unit_price` | number | No | Sell price per unit (what you charge the client). |
| `supplier_uuid` | string | No | UUID of the supplier this cost was purchased from. |
| `date` | string | No | Date of the cost in ISO 8601 format. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the cost was created. |
| `cost` | object | The created cost entry record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

### Purchase Orders

#### `list_purchase_orders`

List purchase orders with optional filtering by date range or supplier.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | No | Start of the date range in ISO 8601 format. |
| `to_date` | string | No | End of the date range in ISO 8601 format. |
| `supplier_uuid` | string | No | Filter to purchase orders for this supplier UUID only. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if purchase orders were retrieved. |
| `purchase_orders` | array | List of purchase order objects. |
| `error` | string | Error message if `result` is `false`. |

---

#### `create_purchase_order`

Create a new purchase order for a supplier, optionally linked to a job.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `supplier_uuid` | string | Yes | UUID of the supplier to raise the purchase order with. |
| `date` | string | Yes | Purchase order date in ISO 8601 format. |
| `amount` | number | Yes | Total order amount excluding tax. |
| `job_uuid` | string | No | UUID of the job this purchase order is associated with. |
| `delivery_date` | string | No | Expected delivery date in ISO 8601 format. |
| `description` | string | No | Description of what is being ordered. |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | `true` if the purchase order was created. |
| `purchase_order` | object | The created purchase order record including its UUID. |
| `error` | string | Error message if `result` is `false`. |

---

## Requirements

```
autohive-integrations-sdk~=1.0.2
```

## API Info

- **Base URL:** `https://api.workflowmax.com/v2`
- **API Version:** v2
- **Docs:** [api-docs.workflowmax.com](https://api-docs.workflowmax.com)
- **Developer Portal:** [developer.workflowmax.com](https://developer.workflowmax.com)

## Rate Limiting

WorkflowMax enforces rate limits per organisation. Check the `X-RateLimit-Remaining` header in responses to monitor usage. When the limit is reached, the API returns `429 Too Many Requests` with a `Retry-After` header indicating when to retry.

## Error Handling

All actions return `{"result": false, "error": "<message>"}` on failure rather than raising exceptions. Common API-level errors:

| HTTP Status | Meaning | Action |
|-------------|---------|--------|
| `401 Unauthorized` | Access token expired or invalid | Re-authenticate via Autohive |
| `403 Forbidden` | Insufficient scope or permissions | Ensure `workflowmax` scope was granted |
| `404 Not Found` | Requested resource does not exist | Verify the UUID is correct for this organisation |
| `422 Unprocessable Entity` | Validation error in request body | Check required fields and data formats |
| `429 Too Many Requests` | Rate limit hit | Wait and retry; observe `Retry-After` header |
| `500 Server Error` | WorkflowMax internal error | Retry; contact support if persistent |

## Troubleshooting

**`401 Unauthorized` after working previously**
Access tokens expire after 30 minutes. Autohive handles refresh automatically via `offline_access`. If refresh fails (refresh token expired after 60 days), reconnect the integration.

**`404 Not Found` for a UUID I just created**
Confirm you're using the UUID returned in the create response, not an ID from a different organisation or environment.

**`403 Forbidden` on all requests**
The OAuth consent may not have included the `workflowmax` scope. Disconnect and reconnect the integration, ensuring all requested scopes are approved.

**Empty `clients` / `jobs` arrays**
Your organisation may have no data, or the account connected may not have permission to view that resource. Check WorkflowMax roles and permissions.

**`add_timesheet` returns an error about task not found**
The `task_uuid` must be a task that belongs to the specified `job_uuid`. Use `list_tasks` with `job_uuid` to find valid task UUIDs for a job.

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 1.0.0 | 2026-04-09 | Initial release — 28 actions covering clients, jobs, timesheets, invoices, quotes, tasks, staff, leads, costs, and purchase orders. |
