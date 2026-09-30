# JobAdder Integration

Connect Autohive workflows to JobAdder's recruitment management API. The integration covers the core recruitment lifecycle plus client relationship reporting: finding jobs, candidates, contacts and companies; reading contact activity; adding candidates to jobs; inspecting applications; and reporting on placements.

## Authentication

This integration uses JobAdder OAuth 2.0 through Autohive. It requests only the scopes used by the shipped actions:

- `read_user`
- `read_job`
- `read_candidate` and `write_candidate`
- `read_contact`, `read_company`, and `read_note`
- `read_contact_note`, `read_candidate_note`, `read_job_note`, `read_jobapplication_note`, `read_placement_note`, and `read_company_note`
- `read_jobapplication` and `write_jobapplication`
- `read_placement`
- `offline_access` so Autohive can refresh JobAdder's 60-minute access tokens

JobAdder returns the account's API base URL during OAuth. Autohive stores that URL as connection metadata; the integration requires it and validates that it is an HTTPS `jobadder.com` URL before making requests. Reconnect accounts created before this metadata was available.

API access requires a JobAdder developer application and approval. See the [JobAdder API documentation](https://developers.jobadder.com/docs/) and [OAuth 2.0 guide](https://jobadderapi.zendesk.com/hc/en-us/articles/360022196774-OAuth2-Authentication).

## Actions

### Account

- `get_current_user` — return the JobAdder user who authorised the connection.

### Jobs

- `list_jobs` — filter jobs by title, company, status, owner, active state, creation/update time, and sort order. Supports offset/limit pagination.
- `get_job` — retrieve full details for one job.
- `list_job_applications` and `list_job_active_applications` — list all or only active applications for a job.
- `list_job_placements` and `list_job_approved_placements` — list all or only approved placements for a job.
- `list_job_attachments`, `list_job_notes`, and `list_job_activities` — retrieve a job's related files, full-text notes, and activity records.

### Candidates

- `list_candidates` — search by name, email, phone, resume keywords, status, recruiter, creation/update time, and sort order.
- `get_candidate` — retrieve a full candidate profile.
- `create_candidate` — create a candidate with optional identity, contact, status, source, skills, recruiter, employment, availability, education, address, social, and custom-field data. JobAdder does not require first and last names in its published request schema. A duplicate override code from a prior HTTP 409 response can be supplied when duplication is intentional.
- `list_candidate_applications` and `list_candidate_active_applications` — list all or only active applications for a candidate.
- `list_candidate_placements` and `list_candidate_approved_placements` — list all or only approved placements for a candidate.
- `list_candidate_attachments`, `list_candidate_skills`, `get_candidate_availability`, and `list_candidate_notes` — retrieve supporting candidate records and full-text notes.

### Contacts and companies

- `list_contacts` — find contacts by company ID or company name, contact name, email, phone, creator/consultant, status, hiring-manager flag, and audit dates. Company-name searches first resolve matching JobAdder company IDs.
- `get_contact` — retrieve full details for one contact.
- `list_companies` — find companies by name, status, creator/consultant, and audit dates.
- `get_company` — retrieve full details for one company.
- `list_contact_jobs` — list the jobs associated with one contact.
- `list_company_contacts` and `list_company_addresses` — retrieve a company's people and locations.
- `list_company_jobs` and `list_company_active_jobs` — list all or only active jobs for a company.
- `list_company_placements` and `list_company_approved_placements` — list all or only approved placements for a company.
- `list_company_attachments` and `list_company_notes` — retrieve company files and full-text notes.

### Contact notes and activities

- `list_contact_notes` — return the notes attached to one contact. JobAdder returns note summaries here, including type, text preview, created date, and creating consultant.
- `list_contact_activities` — search one contact's activities through JobAdder's global notes API, optionally filtering by activity type and creation/update date ranges. Full note text is requested, and results default to newest first.
- `list_all_contact_activities` — search activities linked to up to 100 supplied contact IDs over a required creation date range. This reporting-oriented action supports type filters, pagination, and sorting.
- `get_note` — retrieve one complete note/activity record, including full text and linked records.

The contact reporting actions treat contact-linked notes as CRM activity. `list_all_contact_activities` sends the supplied IDs through JobAdder's `contactId` filter so notes linked only to other record types are excluded.

### Applications

- `list_applications` — filter applications by candidate, job, status, job title, activity, rejection, resume keywords, creation/update time, and sort order.
- `get_application` — retrieve one application.
- `add_candidates_to_job` — add one or more existing candidates to a job, creating applications.
- `list_application_attachments`, `list_application_notes`, and `list_application_activities` — retrieve an application's related files, full-text notes, and activity records.

### Placements

- `list_placements` — filter placements by candidate, job, company, status, approval state, and creation/update time.
- `get_placement` — retrieve one placement.
- `list_placement_attachments`, `list_placement_notes`, and `list_placement_activities` — retrieve a placement's related files, full-text notes, and activity records.
- `list_placement_timesheets` — list placement timesheets, optionally constrained to an inclusive date range.

## Pagination and date filters

Paginated list actions default to `offset: 0` and `limit: 100`; JobAdder permits limits up to 1000. A limit of `0` returns only the total count.

JobAdder date filters accept ISO 8601 values. Prefix a date with `>` or `<` to set an inclusive lower or upper boundary, for example `>2026-01-01T00:00:00Z`.

## Response format

List actions return the records, `total_count`, and JobAdder's pagination `links`. Detail and create actions return the provider object without reshaping its fields, preserving custom fields and links supplied by JobAdder.

## Example workflows

- Find open engineering roles with `list_jobs` using `{"job_title": "Engineer", "active": true}`.
- Create a candidate with `create_candidate` using `{"first_name": "Alex", "last_name": "Smith", "email": "alex@example.com"}`.
- Add that candidate to a job with `add_candidates_to_job` using `{"job_id": 123, "candidate_ids": [456], "source": "Autohive"}`.
- Find contacts created by a consultant with `list_contacts` using `{"company_id": 123, "created_by_user_id": 7}`.
- Build a monthly activity report with `list_all_contact_activities` using `{"contact_ids": [123, 456], "created_at_from": "2026-09-01T00:00:00Z", "created_at_to": "2026-09-30T23:59:59Z"}`.

## Testing

Run the mocked suite from the repository root:

```bash
pytest jobadder/tests -m unit -v
```

The unit tests cover every action, request URLs and methods, query and body mapping, false and zero values, pagination defaults, tenant URL validation, response mapping, and provider-error conversion.

Read-only live tests are opt-in and require the `JOBADDER_ACCESS_TOKEN` and `JOBADDER_API_URL` values documented in the repository-root `.env.example`. The access token expires after 60 minutes, so obtain a fresh token before running them. Detail tests also require IDs for existing test records.

```bash
pytest jobadder/tests/test_jobadder_integration.py -m "integration and not destructive"
```

The two write actions are deliberately excluded from live tests. JobAdder does not expose matching delete operations for candidates or applications, so a test could not reliably clean up the records it creates.

## Important limitations

- API access is controlled by JobAdder and may require partner/developer approval.
- Rate limits are applied per JobAdder account. The SDK handles ordinary request transport and errors, but workflows should avoid unnecessarily aggressive polling.
- Related-record actions are read-only. The integration does not create or update contacts, companies, notes, activities, attachments, placements, or timesheets.
- The integration does not manage job records, application statuses, requisitions, job ads, partner actions, or webhooks.
