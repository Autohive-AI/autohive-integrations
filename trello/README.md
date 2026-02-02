# Trello Integration for Autohive

Connects Autohive to the Trello API to enable board management, list organization, card tracking, and team collaboration automation.

## Description

This integration provides a comprehensive connection to Trello's project management platform. It allows users to automate card creation, board management, list organization, and workflow automation directly from Autohive.

The integration uses Trello REST API v1 with API Key and Token authentication and implements 17 comprehensive actions covering members, boards, lists, cards, checklists, and comments.

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

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields (e.g., `board`, `card`, `list`)

Example successful response:
```json
{
  "result": true,
  "board": { "id": "abc123", "name": "My Board" }
}
```

Example error response:
```json
{
  "result": false,
  "error": "Board not found",
  "board": {}
}
```

## Actions

### Members (1 action)

#### `get_current_member`
Returns information about the authenticated member.

**Inputs:**
- None required

**Outputs:**
- `member`: Member object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_board`
Retrieves details of a specific board by its ID.

**Inputs:**
- `board_id` (required): The ID of the board
- `fields` (optional): Comma-separated list of fields to return (e.g., 'name,desc,url')

**Outputs:**
- `board`: Board object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `list_boards`
Returns all boards for the authenticated member.

**Inputs:**
- `filter` (optional): Filter boards - "all", "open", "closed", "members", "organization", "public", "starred" (default: "open")

**Outputs:**
- `boards`: Array of board objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_list`
Retrieves details of a specific list by its ID.

**Inputs:**
- `list_id` (required): The ID of the list

**Outputs:**
- `list`: List object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `list_lists`
Returns all lists on a board.

**Inputs:**
- `board_id` (required): The ID of the board
- `filter` (optional): Filter lists - "all", "open", "closed" (default: "open")

**Outputs:**
- `lists`: Array of list objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Cards (5 actions)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_card`
Retrieves details of a specific card by its ID.

**Inputs:**
- `card_id` (required): The ID of the card
- `fields` (optional): Comma-separated list of fields to return

**Outputs:**
- `card`: Card object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_card`
Deletes a card permanently.

**Inputs:**
- `card_id` (required): The ID of the card to delete

**Outputs:**
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `list_cards`
Returns all cards on a list or board.

**Inputs:**
- `list_id` (optional): The ID of the list (use this or board_id)
- `board_id` (optional): The ID of the board (use this or list_id)
- `filter` (optional): Filter cards - "all", "open", "closed", "visible" (default: "open")

**Note:** Either `list_id` or `board_id` is required.

**Outputs:**
- `cards`: Array of card objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Checklists (2 actions)

#### `create_checklist`
Creates a new checklist on a card.

**Inputs:**
- `card_id` (required): The ID of the card
- `name` (required): The name of the checklist

**Outputs:**
- `checklist`: Created checklist object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Comments (1 action)

#### `add_comment`
Adds a comment to a card.

**Inputs:**
- `card_id` (required): The ID of the card
- `text` (required): The comment text (supports Markdown)

**Outputs:**
- `comment`: Created comment object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

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

To test the integration:

1. Navigate to the integration directory: `cd trello`
2. Install dependencies: `pip install -r requirements.txt`
3. Update test file with your credentials: `tests/test_trello.py`
4. Run tests: `python tests/test_trello.py`

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

- **1.0.0** - Initial release with 17 comprehensive actions
  - Members: get_current_member (1 action)
  - Boards: create, get, update, list (4 actions)
  - Lists: create, get, update, list (4 actions)
  - Cards: create, get, update, delete, list (6 actions)
  - Checklists: create_checklist, add_checklist_item (2 actions)
  - Comments: add_comment (1 action)
