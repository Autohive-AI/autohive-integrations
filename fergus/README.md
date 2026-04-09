# Fergus Integration for Autohive

Manage jobs in Fergus for field service and trade workflows — covering the inbound MP work order flow
and the outbound BCTI reporting flow.

## Setup & Authentication

- Auth type: Personal Access Token (PAT)
- Generate your token from **Settings → Fergus API** inside your Fergus account.
- Field required: `api_token` (password)

## Actions

### create_job
Creates a new job in Fergus from an inbound work order.

Set `is_draft: true` to create a draft first (only `job_type` and `title` required), then use
`update_job` to fill in customer/site details, then `finalise_job` to make it active.

For a direct non-draft job, all fields below are required by Fergus.

**Required:** `job_type` (Quote | Estimate | Charge Up), `title`
**Required for non-draft:** `description`, `customer_id`, `site_id`
**Optional:** `customer_reference` (MP work order ref), `is_draft`

---

### update_job
Updates a **draft** job in Fergus. Fergus only allows updating jobs that are still in draft status.
Call `finalise_job` after to make the job active.

**Required:** `job_id`
**Optional:** `job_type`, `title`, `description`, `customer_id`, `site_id`, `customer_reference`

---

### finalise_job
Finalises a draft job, making it active and ready to assign to a technician.

**Required:** `job_id`

---

### get_job
Retrieves full details of a single job, including completion and invoice data for BCTI reporting.

**Required:** `job_id`

---

### list_jobs
Lists jobs with optional filters. Use `status: Completed` or `status: Invoiced` to pull jobs ready
for BCTI outbound reporting back to maintenance partners.

**Optional:** `status` (Active | Completed | Invoiced), `job_type`, `customer_id`, `site_id`,
`job_number`, `search`, `sort_order` (asc | desc), `page_size`, `page_cursor`

---

### search_customers
Search for customers by name. Use this to find a `customer_id` before creating a job.

**Optional:** `search`, `sort_order`, `page_size`, `page_cursor`

---

### get_customer
Get full details of a single customer.

**Required:** `customer_id`

---

### list_sites
List sites (job locations). Use to find a `site_id` before creating a job.

**Optional:** `search`, `sort_order`, `page_size`, `page_cursor`

---

### list_users
List all users (technicians and staff). Use to find user IDs when assigning jobs.

**Optional:** `search`, `sort_order`, `page_size`, `page_cursor`

---

## Typical Agent Workflow

**Inbound — MP work order → Fergus job:**
1. `search_customers` — find the customer by name
2. `list_sites` — find the site for that customer
3. `create_job` — create the job with all details
4. _(optional)_ `list_users` + calendar event to assign a technician

**Outbound — Fergus → MP portal (BCTI):**
1. `list_jobs` with `status: Invoiced`
2. `get_job` — pull full invoice/completion details
3. Push data to the MP portal via their integration

## Notes

- The Fergus API enforces a rate limit of 100 requests per minute per company.
- Endpoint paths are based on `https://api.fergus.com`. Verify against the Swagger docs at
  `https://api.fergus.com/docs` if any endpoint returns unexpected errors.

