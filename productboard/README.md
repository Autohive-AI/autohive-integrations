# Productboard Integration

Productboard integration for managing features, products, components, notes, and customer feedback.

## Overview

This integration connects to the Productboard API v2 to manage product hierarchy entities (features, products, components, initiatives, objectives, releases) and notes (customer feedback, conversations).

## Authentication

This integration uses OAuth2 authentication via the Autohive platform. Users connect their Productboard workspace through the platform's OAuth flow.

### Required Scopes

- `product_hierarchy_data:read` - Read features, products, components
- `product_hierarchy_data:create` - Create features and entities
- `product_hierarchy_data:manage` - Update entities
- `custom_fields:read` - Read custom field definitions
- `notes:read` - Read notes/feedback
- `notes:create` - Create notes
- `notes:manage` - Update notes
- `users:read` - Read user information
- `companies:read` - Read company information
- `companies:create` - Create companies
- `companies:manage` - Update companies

## Actions

### Entity Actions

| Action | Description |
|--------|-------------|
| `list_entities` | List entities (features, products, components, initiatives, etc.) with filtering |
| `get_entity` | Get a specific entity by ID |
| `create_entity` | Create a new entity |
| `update_entity` | Update an existing entity |
| `get_entity_configuration` | Get metadata about entity fields and validation rules |

### Note Actions

| Action | Description |
|--------|-------------|
| `list_notes` | List notes with filtering by owner, dates, status |
| `get_note` | Get a specific note by ID |
| `create_note` | Create a new note (simple or conversation) |
| `update_note` | Update an existing note |
| `get_note_configuration` | Get metadata about note fields |

### Analytics Actions

| Action | Description |
|--------|-------------|
| `list_analytics_reports` | List available analytics reports |
| `get_analytics_report` | Get a specific analytics report |

### User Actions

| Action | Description |
|--------|-------------|
| `get_current_user` | Get information about the authenticated user |

## Entity Types

The integration supports these Productboard entity types:
- `product` - Top-level product
- `component` - Product component
- `feature` - Product feature
- `subfeature` - Feature sub-item
- `initiative` - Strategic initiative
- `objective` - Product objective
- `keyResult` - Key result for objectives
- `release` - Release/version
- `releaseGroup` - Group of releases

## Note Types

- `simple` - Standard feedback note
- `conversation` - Multi-message conversation (e.g., support chat)
- `opportunity` - Structured opportunity (read-only via API)

## Usage Examples

### List Features

```python
result = await integration.execute("list_entities", {
    "type": "feature",
    "archived": False
})
```

### Create a Feature

```python
result = await integration.execute("create_entity", {
    "type": "feature",
    "name": "New Feature",
    "description": "Feature description",
    "parent_id": "parent-component-id"
})
```

### Create a Note

```python
result = await integration.execute("create_note", {
    "type": "simple",
    "name": "Customer Feedback",
    "content": "User requested dark mode support",
    "tags": ["feedback", "ui"],
    "customer_email": "customer@example.com"
})
```

### Update a Note

```python
result = await integration.execute("update_note", {
    "note_id": "note-uuid",
    "processed": True,
    "tags_to_add": ["reviewed"]
})
```

## API Reference

This integration uses the Productboard REST API v2 (Beta).

- Base URL: `https://api.productboard.com/v2`
- Rate Limit: 50 requests per second per access token
- [API Documentation](https://developer.productboard.com/v2.0.0/reference/introduction)

## Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests

```bash
python -m pytest tests/ -v
```
