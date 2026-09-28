# JobAdder Integration

Connect Autohive workflows to JobAdder's recruitment management API. The integration covers the core recruitment lifecycle: finding jobs, finding or creating candidates, adding candidates to jobs, inspecting applications, and reporting on placements.

## Authentication

This integration uses JobAdder OAuth 2.0 through Autohive. It requests only the scopes used by the shipped actions:

- `read_user`
- `read_job`
- `read_candidate` and `write_candidate`
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

### Candidates

- `list_candidates` — search by name, email, phone, resume keywords, status, recruiter, creation/update time, and sort order.
- `get_candidate` — retrieve a full candidate profile.
- `create_candidate` — create a candidate with optional identity, contact, status, source, skills, recruiter, employment, availability, education, address, social, and custom-field data. JobAdder does not require first and last names in its published request schema. A duplicate override code from a prior HTTP 409 response can be supplied when duplication is intentional.

### Applications

- `list_applications` — filter applications by candidate, job, status, job title, activity, rejection, resume keywords, creation/update time, and sort order.
- `get_application` — retrieve one application.
- `add_candidates_to_job` — add one or more existing candidates to a job, creating applications.

### Placements

- `list_placements` — filter placements by candidate, job, company, status, approval state, and creation/update time.
- `get_placement` — retrieve one placement.

## Pagination and date filters

List actions default to `offset: 0` and `limit: 100`; JobAdder permits limits up to 1000. A limit of `0` returns only the total count.

JobAdder date filters accept ISO 8601 values. Prefix a date with `>` or `<` to set an inclusive lower or upper boundary, for example `>2026-01-01T00:00:00Z`.

## Response format

List actions return the records, `total_count`, and JobAdder's pagination `links`. Detail and create actions return the provider object without reshaping its fields, preserving custom fields and links supplied by JobAdder.

## Example workflows

- Find open engineering roles with `list_jobs` using `{"job_title": "Engineer", "active": true}`.
- Create a candidate with `create_candidate` using `{"first_name": "Alex", "last_name": "Smith", "email": "alex@example.com"}`.
- Add that candidate to a job with `add_candidates_to_job` using `{"job_id": 123, "candidate_ids": [456], "source": "Autohive"}`.

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
- This initial release does not manage job records, application statuses, placements, notes, files, requisitions, job ads, partner actions, or webhooks.
