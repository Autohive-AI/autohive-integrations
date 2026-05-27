# Trello Integration for Autohive

Connects Autohive to the Trello API to enable board management, list organization, card tracking, and team collaboration automation.

## Description

This integration provides a comprehensive connection to Trello's project management platform. It allows users to automate card creation, board management, list organization, and workflow automation directly from Autohive.

The integration uses Trello REST API v1 with API Key and Token authentication and implements 18 actions covering members, boards, lists, cards (including search), checklists, and comments.

Built against `autohive-integrations-sdk ~= 2.0.0`. Handlers return an `ActionResult` on success and an `ActionError(message=...)` on failure — there is no more `result: false / error: "..."` envelope in the action output.

## Setup & Authentication

This integration uses **custom authentication** with Trello API Key and Token for secure access to your Trello account.

### Authentication Method

The integration uses API Key and Token authentication:
- **API Key** - Your public Trello API Key
- **API Token** - Your secret Trello API Token with required permissions

### Setup Steps

#### 1. Get Your API Key

1. Visit https://trello.com/power-ups/admin
2. Select your Power-Up or create a new one
3. Navigate to the "API Key" tab
4. Generate a new API Key if you haven't already
5. Copy your API Key

#### 2. Get Your API Token

1. After obtaining your API Key, click the "Token" link on the same page
2. Authorize the application to access your Trello account
3. Select the permissions you want to grant:
   - Read access to your boards and cards
   - Write access to create/update boards, lists, and cards
   - Account access to read your member information
4. Copy the generated token

#### 3. Configure in Autohive

1. Add Trello integration in Autohive
2. Enter your API Key in the "API Key" field
3. Enter your API Token in the "API Token" field
4. Save your credentials

The integration will use these credentials for all API requests.

## Action Results

Handlers return:
- `ActionResult(data=...)` on success — the `data` payload contains only the action-specific fields (e.g. `board`, `card`, `cards`, `count`).
- `ActionError(message="...")` on failure (non-2xx Trello responses, missing required inputs, network errors, etc.). The Autohive runtime surfaces `ActionError.message` to the caller; the action's `output_schema` describes only the success shape.

Example successful response (`get_board`):
```json
{ "board": { "id": "abc123", "name": "My Board" } }
```

Example successful list response (`list_cards`):
```json
{ "cards": [{ "id": "c1", "name": "First card" }], "count": 1 }
```

Example failure: an `ActionError` is returned with `message`, e.g. `"Board not found"`.

## Actions

### Members (1 action)

#### `get_current_member`
Returns information about the authenticated member.

**Inputs:**
- None required

**Outputs:**
- `member`: Member object with details

---

### Boards (4 actions)

#### `create_board`
Creates a new board in Trello.

**Inputs:**
- `name` (required): Board name
- `desc` (optional): Board description
- `defaultLists` (optional): Whether to create default lists (To Do, Doing, Done) - default: true
- `prefs_permissionLevel` (optional): Permission level - "private", "org", or "public"
- `prefs_background` (optional): Board background color (e.g., 'blue', 'green', 'red')

**Outputs:**
- `board`: Created board object

---

#### `get_board`
Retrieves details of a specific board by its ID.

**Inputs:**
- `board_id` (required): The ID of the board
- `fields` (optional): Comma-separated list of fields to return (e.g., 'name,desc,url')

**Outputs:**
- `board`: Board object with details

---

#### `update_board`
Updates an existing board's details.

**Inputs:**
- `board_id` (required): The ID of the board to update
- `name` (optional): Updated board name
- `desc` (optional): Updated board description
- `closed` (optional): Whether the board is closed (archived)
- `prefs_permissionLevel` (optional): Permission level: private, org, or public

**Outputs:**
- `board`: Updated board object

---

#### `list_boards`
Returns all boards for the authenticated member.

**Inputs:**
- `filter` (optional): Filter boards - "all", "open", "closed", "members", "organization", "public", "starred" (default: "open")

**Outputs:**
- `boards`: Array of board objects

---

### Lists (4 actions)

#### `create_list`
Creates a new list on a board.

**Inputs:**
- `board_id` (required): The ID of the board
- `name` (required): The name of the list
- `pos` (optional): Position - "top", "bottom", or a positive number

**Outputs:**
- `list`: Created list object

---

#### `get_list`
Retrieves details of a specific list by its ID.

**Inputs:**
- `list_id` (required): The ID of the list

**Outputs:**
- `list`: List object with details

---

#### `update_list`
Updates a list's properties.

**Inputs:**
- `list_id` (required): The ID of the list to update
- `name` (optional): Updated list name
- `closed` (optional): Whether the list is closed (archived)
- `pos` (optional): New position - "top", "bottom", or a positive number

**Outputs:**
- `list`: Updated list object

---

#### `list_lists`
Returns all lists on a board.

**Inputs:**
- `board_id` (required): The ID of the board
- `filter` (optional): Filter lists - "all", "open", "closed" (default: "open")

**Outputs:**
- `lists`: Array of list objects

---

### Cards (6 actions)

#### `create_card`
Creates a new card on a list.

**Inputs:**
- `list_id` (required): The ID of the list
- `name` (required): The name of the card
- `desc` (optional): Card description (supports Markdown)
- `pos` (optional): Position - "top", "bottom", or a positive number
- `due` (optional): Due date (ISO 8601 format)
- `idMembers` (optional): Array of member IDs to assign to the card
- `idLabels` (optional): Array of label IDs to add to the card

**Outputs:**
- `card`: Created card object

---

#### `get_card`
Retrieves details of a specific card by its ID.

**Inputs:**
- `card_id` (required): The ID of the card
- `fields` (optional): Comma-separated list of fields to return

**Outputs:**
- `card`: Card object with details

---

#### `update_card`
Updates an existing card's details.

**Inputs:**
- `card_id` (required): The ID of the card to update
- `name` (optional): Updated card name
- `desc` (optional): Updated card description
- `closed` (optional): Whether the card is closed (archived)
- `idList` (optional): Move card to a different list (list ID)
- `due` (optional): Updated due date (ISO 8601)
- `dueComplete` (optional): Whether the due date is marked complete
- `idMembers` (optional): Updated array of member IDs

**Outputs:**
- `card`: Updated card object

---

#### `delete_card`
Deletes a card permanently.

**Inputs:**
- `card_id` (required): The ID of the card to delete

**Outputs:**

---

#### `list_cards`
Returns cards on a list or board with **cursor-based pagination**. Uses Trello's documented `limit` + `before`/`since` parameters on `/lists/{id}/cards` and `/boards/{id}/cards` (see [Atlassian's Paging guide](https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/#paging)). Use `search_cards` for name-based lookups.

**Inputs:**
- `list_id` (optional): The ID of the list (use this or board_id)
- `board_id` (optional): The ID of the board (use this or list_id)
- `filter` (optional): Filter cards - "all", "open", "closed", "visible" (default: "open")
- `limit` (optional): Server-side cap on cards per request, 1-1000 (default: 50)
- `before` (optional): Cursor — only return cards created before this card ID or ISO 8601 date. Pass the previous response's `next_before` here to fetch the next page.
- `since` (optional): Cursor — only return cards created after this card ID or ISO 8601 date.
- `fields` (optional): Comma-separated card fields, or "all" (default: compact set). Enforced client-side as well as via the API.

**Note:** Either `list_id` or `board_id` is required.

**Outputs:**
- `cards`: Array of card objects
- `count`: Number of cards returned
- `next_before` (optional): Cursor for the next page (the lexicographically smallest card ID in this response, i.e. the oldest-created card). Present only when a full page was returned, indicating more cards may exist. Pass back as `before` to paginate.

**Pagination example:**
```
list_cards(board_id="b1", limit=50)         # → 50 cards + next_before="cZ"
list_cards(board_id="b1", limit=50, before="cZ")  # → next 50 + maybe next_before
# Continue until response has no next_before.
```

---

#### `search_cards`
Searches Trello cards by name/text or advanced Trello search query. Use this when you don't know which board or list contains the card. Backed by `GET /1/search?modelTypes=cards`.

**Inputs:**
- `card_name` (optional): Card name/text to search for (wrapped in Trello's `name:"..."` operator)
- `query` (optional): Advanced Trello search query (e.g. `name:"Bug" list:"In Progress" label:red due:week`). Combined with `card_name` if both are given.
- `board_id` (optional): Scope search to a board (sent as `idBoards`)
- `organization_id` (optional): Scope search to a workspace/organization
- `open_only` (optional): Restrict to open cards by appending `is:open` (default: true)
- `partial` (optional): Enable prefix matching, e.g. "dev" matches "Development" (default: true)
- `limit` (optional): Max cards to return, 1-1000 (default: 10)
- `page` (optional): Page of card search results for pagination (default: 0)
- `fields` (optional): Comma-separated card fields, or "all"
- `include_board` (optional): Include board on each card (default: true)
- `include_list` (optional): Include list on each card (default: true)
- `include_members` (optional): Include members on each card (default: false)
- `include_attachments` (optional): Include attachments on each card (default: false)

**Note:** Either `card_name` or `query` is required.

**Outputs:**
- `cards`: Array of matching card objects
- `count`: Number of cards returned
- `options`: Trello search metadata/options

---

### Checklists (2 actions)

#### `create_checklist`
Creates a new checklist on a card.

**Inputs:**
- `card_id` (required): The ID of the card
- `name` (required): The name of the checklist

**Outputs:**
- `checklist`: Created checklist object

---

#### `add_checklist_item`
Adds a new item to a checklist.

**Inputs:**
- `checklist_id` (required): The ID of the checklist
- `name` (required): The name/text of the checklist item
- `checked` (optional): Whether the item is checked (default: false)
- `pos` (optional): Position - "top", "bottom", or a positive number

**Outputs:**
- `checkItem`: Created checklist item object

---

### Comments (1 action)

#### `add_comment`
Adds a comment to a card.

**Inputs:**
- `card_id` (required): The ID of the card
- `text` (required): The comment text (supports Markdown)

**Outputs:**
- `comment`: Created comment object

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v1
- **Base URL**: `https://api.trello.com/1`
- **Authentication**: API Key + Token
- **Documentation**: https://developer.atlassian.com/cloud/trello/rest/
- **Rate Limits**:
  - Free accounts: 300 requests per 10 seconds per API key
  - Requests are rate-limited per token, per API key

## Important Notes

- API Key and Token are passed as query parameters in all requests
- Card descriptions and comments support Markdown formatting
- Position values can be "top", "bottom", or a positive number
- Member IDs and Label IDs should be provided as arrays when creating or updating cards
- All date/time values should be in ISO 8601 format
- IDs in Trello are alphanumeric strings (not numeric GIDs like Asana)

## Testing

Unit tests (mocked, CI-safe, no credentials required):

```bash
pytest trello/tests/test_trello_unit.py
```

Live integration smoke tests (opt-in; require real Trello credentials):

```bash
export TRELLO_API_KEY=your_api_key
export TRELLO_API_TOKEN=your_api_token
pytest trello/tests/test_trello_integration.py -m integration
```

The integration tests are skipped automatically if `TRELLO_API_KEY` / `TRELLO_API_TOKEN` are unset, and they never run in CI (the project's default pytest discovery only picks up `test_*_unit.py`).

## Common Use Cases

**Board Management:**
1. List all boards for the authenticated user
2. Create new boards for projects
3. Update board names and descriptions
4. Archive completed boards

**List Organization:**
1. Create lists for workflow stages (To Do, In Progress, Done)
2. Update list names
3. Reorder lists on a board
4. Archive unused lists

**Card Management:**
1. Create cards from external triggers (emails, forms, etc.)
2. Update card details as work progresses
3. Move cards between lists
4. Assign cards to team members
5. Set due dates and mark them complete
6. Delete obsolete cards

**Checklist Tracking:**
1. Create checklists for task breakdowns
2. Add checklist items for subtasks
3. Mark items as complete

**Team Communication:**
1. Add comments to cards for updates
2. Document decisions and discussions
3. Provide status updates

**Workflow Automation:**
1. Auto-create cards from external events
2. Move cards through workflow stages
3. Auto-assign cards based on rules
4. Update card status based on checklist completion
5. Archive completed cards automatically

## Version History

- **2.0.0**
  - Upgraded to `autohive-integrations-sdk ~= 2.0.0`.
  - `context.fetch()` now returns a `FetchResponse`; all handlers were updated to read `response.data` and to check `response.status` so non-2xx responses no longer silently look successful.
  - **Breaking:** handlers now return `ActionError(message=...)` on failure instead of `{ "result": false, "error": "..." }`. Success payloads no longer carry `result: true`. Output schemas were updated to match.
  - Added `search_cards` action backed by `GET /1/search`. Translates `card_name` into Trello's `name:"..."` operator, accepts an advanced `query`, defaults to `is:open` (skipped when the user already specifies `is:open|closed|archived`), and limits results (default 10).
  - `list_cards` now uses Trello's server-side `limit` + `before`/`since` cursor pagination on `/lists/{id}/cards` and `/boards/{id}/cards`, and returns a `next_before` cursor when more results are likely available. Default limit is 50; max 1000. Compact default field set; field projection is enforced client-side.
  - `delete_card` now returns `{ "deleted": true, "card_id": "..." }` on success.
  - Added unit test suite at `tests/test_trello_unit.py` covering the v2 contract, ActionError on non-2xx, the `is:open` injection logic, slicing, and field projection.
- **1.0.0** - Initial release with 17 actions
  - Members: get_current_member (1 action)
  - Boards: create, get, update, list (4 actions)
  - Lists: create, get, update, list (4 actions)
  - Cards: create, get, update, delete, list (5 actions)
  - Checklists: create_checklist, add_checklist_item (2 actions)
  - Comments: add_comment (1 action)
