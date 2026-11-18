# Figma

Figma REST API integration for Autohive, using SDK 2.1. Includes 21 actions for design inspection, image export, comments, projects, version history, and published libraries.

## Authentication

1. Open Figma account **Settings > Security > Personal access tokens**.
2. Generate a token, select an expiration, and enable only the scopes needed by your workflows (see the action table).
3. Enter it as **Personal Access Token** in Autohive. The integration sends it in `X-Figma-Token` through `context.fetch()`.

Runtime credential shape:

```json
{"auth_type": "Custom", "credentials": {"personal_access_token": "<your-token>"}}
```

Token permissions cannot exceed the user's access to a resource. Tokens expire; replace expired or revoked tokens in the connected account.

## Actions

Inputs marked required must be supplied. Other inputs are optional. Responses preserve Figma's original JSON fields, including metadata and pagination; the output column lists required result fields. Nested nodes and library records retain their original API shape.

| Action | Inputs | Output fields | Token scope |
|---|---|---|---|
| `get_me` | None | `id`, `email`, `handle` | `current_user:read` |
| `get_file` | `file_key` (required), `version`, `depth`, `geometry`, `plugin_data`, `ids`, `branch_data` | `name`, `document` | `file_content:read` |
| `get_file_nodes` | `file_key` (required), `ids` (required), `version`, `depth`, `geometry`, `plugin_data` | `nodes` | `file_content:read` |
| `get_file_metadata` | `file_key` (required) | `file` | `file_metadata:read` |
| `export_images` | `file_key` (required), `ids` (required), `version`, `format`, `scale`, `svg_outline_text`, `svg_include_id`, `svg_include_node_id`, `svg_simplify_stroke`, `contents_only`, `use_absolute_bounds` | `images` | `file_content:read` |
| `get_image_fills` | `file_key` (required) | `meta` | `file_content:read` |
| `list_comments` | `file_key` (required), `as_md` | `comments` | `file_comments:read` |
| `create_comment` | `file_key` (required), `message` (required), `comment_id`, `client_meta` | `id`, `message` | `file_comments:write` |
| `delete_comment` | `file_key` (required), `comment_id` (required) | `deleted` | `file_comments:write` |
| `list_team_projects` | `team_id` (required) | `projects` | `projects:read` |
| `list_project_files` | `project_id` (required), `branch_data` | `files` | `projects:read` |
| `list_file_versions` | `file_key` (required), `page_size`, `before`, `after` | `versions` | `file_versions:read` |
| `list_file_components` | `file_key` (required) | `meta` | `library_content:read` |
| `list_team_components` | `team_id` (required), `page_size`, `before`, `after` | `meta` | `team_library_content:read` |
| `get_component` | `key` (required) | `meta` | `library_assets:read` |
| `list_file_component_sets` | `file_key` (required) | `meta` | `library_content:read` |
| `list_team_component_sets` | `team_id` (required), `page_size`, `before`, `after` | `meta` | `team_library_content:read` |
| `get_component_set` | `key` (required) | `meta` | `library_assets:read` |
| `list_file_styles` | `file_key` (required) | `meta` | `library_content:read` |
| `list_team_styles` | `team_id` (required), `page_size`, `before`, `after` | `meta` | `team_library_content:read` |
| `get_style` | `key` (required) | `meta` | `library_assets:read` |

## Usage and pagination

A URL such as `https://www.figma.com/design/AbC123/Example?node-id=1-2` has file key `AbC123`. Pass node IDs in API form, such as `1:2`, in the `ids` array. Asset `key` values are published component/style keys, not node IDs. Team/project IDs come from their corresponding browser URLs.

Example inputs:

```json
{"file_key": "AbC123", "depth": 2}
```

```json
{"file_key": "AbC123", "ids": ["1:2"], "format": "png", "scale": 2}
```

```json
{"file_key": "AbC123", "message": "Please review", "client_meta": {"node_id": "1:2", "node_offset": {"x": 20, "y": 30}}}
```

`create_comment` supports unpinned comments, canvas points `{x, y}`, node-relative points `{node_id, node_offset: {x, y}}`, and replies using a root `comment_id`. Region comments are not exposed. Only comments authored by the token owner can be deleted.

Team library and version actions return one page per call. Supply **either** `before` **or** `after`, using the numeric cursor from the previous response. Team library cursors are in `meta.cursor`. Version responses preserve `pagination`; extract the numeric before/after value from its links and pass it to the next call. The integration never fetches arbitrary pagination URLs. File versions allow `page_size` 1â€“50; team libraries allow 1â€“1000. Other list endpoints above are unpaginated.

`export_images` returns an `images` map of node IDs to temporary URLs; null values mean that node could not be rendered. `get_image_fills` returns image reference URLs under `meta.images`. Download exported files before their URLs expire; these actions return URLs rather than Autohive file objects.

Published component/style endpoints return published assets, which may be empty even when unpublished assets exist in the document. General canvas creation and editing are not exposed by these REST actions.

## API and troubleshooting

- Base URL: `https://api.figma.com/v1`.
- [REST API reference](https://developers.figma.com/docs/rest-api/), [personal access tokens](https://developers.figma.com/docs/rest-api/personal-access-tokens/), [scopes](https://developers.figma.com/docs/rest-api/scopes/).
- [Rate limits](https://developers.figma.com/docs/rest-api/rate-limits/) vary by endpoint, seat, and resource plan. SDK HTTP retry handling applies; HTTP 429 errors should be retried according to `Retry-After`, rather than immediately repeating requests.
- 401/403: check token expiration, scopes, and the user's access to the team/file. 404: verify the file key, project ID, or published asset key.
- Use `depth`, `ids`, and metadata-only reads to avoid unnecessarily large documents.
- Expected API failures return `ActionError`; invalid inputs are rejected by the SDK before making a request. Unexpected infrastructure exceptions follow SDK error handling.

## Development

From the repository root, with Python 3.13+ and an activated virtual environment:

```powershell
python -m pip install -r figma/requirements.txt -r requirements-test.txt
python ../autohive-integrations-tooling/scripts/validate_integration.py figma
python ../autohive-integrations-tooling/scripts/check_code.py figma
python -m pytest figma/ -v
```

Unit tests mock SDK `FetchResponse` objects and require no credentials. Live API verification requires a separately provided Figma token and accessible resources; it is not part of the mocked suite.
