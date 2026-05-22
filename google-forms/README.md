# Google Forms

Create and manage Google Forms — author questions, publish, and read responses — from Autohive.

## Auth

Platform OAuth via Google. The integration uses two scopes:

- `https://www.googleapis.com/auth/forms.body` — create and edit forms and their questions
- `https://www.googleapis.com/auth/forms.responses.readonly` — read submitted responses

## Actions

| Action | Purpose |
|---|---|
| `create_form` | Create a new form (title only — Forms API limitation; use `update_form_info` and `add_*_question` afterwards). Sets the `unpublished` query parameter from `auto_publish` (default `true`), so the returned `responder_uri` accepts submissions immediately. Pass `auto_publish: false` to create a draft — the form is created unpublished from the start, both before and after Google's [2026-06-30 default-flip cutoff](https://developers.google.com/workspace/forms/api/guides/api-changes-to-google-forms). |
| `get_form` | Fetch the full form: info, settings, items, metadata. |
| `update_form_info` | Update form title and/or description. |
| `set_publish_settings` | Publish / unpublish the form; toggle whether it accepts responses. |
| `add_text_question` | Append a short-answer or paragraph text question. |
| `add_multiple_choice_question` | Append a `RADIO`, `CHECKBOX`, or `DROP_DOWN` question. |
| `add_scale_question` | Append a linear-scale question with optional anchor labels. |
| `delete_item` | Remove a question by 0-based index. |
| `batch_update_form` | Escape hatch — apply raw `batchUpdate` `Request` objects for anything not covered above. |
| `list_responses` | List submitted responses, paginated. |
| `get_response` | Fetch a single response by ID. |

## Watches (push notifications)

The Forms API supports `forms.watches.*` for push notifications via Cloud Pub/Sub. Not exposed in this version — it requires a pre-existing Pub/Sub topic and IAM setup that don't fit the platform's current connection flow.

## Testing

Unit tests:

```bash
python3 -m pytest google-forms/tests/test_google_forms_unit.py -v
```

Integration tests (live API — needs an OAuth access token in `.env`):

```bash
# Read-only — safe
python3 -m pytest google-forms/tests/test_google_forms_integration.py -m "integration and not destructive" -v

# Destructive — creates and deletes real forms; use a throwaway Google account
python3 -m pytest google-forms/tests/test_google_forms_integration.py -m "integration and destructive" -v
```

Set `GOOGLE_FORMS_ACCESS_TOKEN` in the repo-root `.env`. Get one quickly from the [OAuth Playground](https://developers.google.com/oauthplayground) with the two scopes above.

For comment/response tests there's also an optional `GOOGLE_FORMS_TEST_FORM_ID` — a pre-existing form ID to read from without creating one.
