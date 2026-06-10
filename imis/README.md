# iMIS RiSE

iMIS RiSE is a Content Management System and website-building platform built into iMIS, the membership management software used by associations and non-profits. This integration allows Autohive workflows to manage contacts, events, registrations, and media assets on an iMIS-powered website.

## Auth Setup

This integration uses iMIS OAuth 2.0 (Resource Owner Password Credentials). You will need:

1. **Site URL** — your iMIS site URL (e.g. `https://yourorg.imis.com`)
2. **Username** — your iMIS login username
3. **Password** — your iMIS login password
4. **Client ID** — the OAuth client ID configured in your iMIS instance (default: `iMIS`)

The integration exchanges your credentials for a Bearer token automatically on each action call.

## Actions

| Action | Description | Key Inputs | Key Outputs |
|--------|-------------|------------|-------------|
| `get_contact` | Get a contact by Party ID | `party_id` | `contact` |
| `create_contact` | Create a new contact | `last_name`, `first_name`, `email` | `contact` |
| `update_contact` | Update contact details | `party_id`, `email`, `phone`, `address` | `contact` |
| `list_events` | List events with optional date filters | `limit`, `from_date`, `to_date` | `events`, `count` |
| `get_event` | Get event details by ID | `event_id` | `event` |
| `create_event` | Create a new event | `title`, `start_date` | `event` |
| `update_event` | Update an existing event | `event_id`, `title`, `start_date` | `event` |
| `list_registrations` | List event registrations | `event_id`, `party_id` | `registrations`, `count` |
| `create_registration` | Register a contact for an event | `event_id`, `party_id` | `registration` |
| `delete_registration` | Cancel an event registration | `registration_id` | `deleted` |
| `list_groups` | List groups | `limit`, `offset` | `groups`, `count` |
| `get_group` | Get group details by ID | `group_id` | `group` |
| `add_group_member` | Add a contact to a group | `group_id`, `party_id` | `member` |
| `remove_group_member` | Remove a contact from a group | `group_id`, `party_id` | `deleted` |
| `list_tags` | List all available tags | `limit`, `offset` | `tags`, `count` |
| `add_tag` | Add a tag to a contact | `party_id`, `tag` | `tag` |
| `run_query` | Run a saved IQA query | `query_name`, `parameters` | `results`, `count` |
| `list_media_assets` | List media assets (images, files) | `limit`, `search` | `assets`, `count` |
| `get_media_asset` | Get a media asset by ID | `asset_id` | `asset` |

## API Info

- **Base URL:** `https://yoursite.com/api/`
- **Token URL:** `https://yoursite.com/token/`
- **Docs:** [iMIS Developer Portal](https://developer.imis.com)
- **API version:** iMIS 2017 Service Pack F+

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to obtain iMIS access token` | Wrong credentials or site URL | Verify site URL, username, password, and client ID |
| `401 Unauthorized` | Token expired or invalid | Check credentials; token is refreshed per action call |
| `404 Not Found` | Invalid Party ID or Event ID | Confirm the ID exists in your iMIS instance |
| `403 Forbidden` | User lacks permission for the resource | Use an admin account or grant the user appropriate iMIS permissions |
