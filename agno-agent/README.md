# Agno Data Agent Integration for Autohive

Connects Autohive to an [Agno AgentOS](https://docs.agno.com/agent-os/api) data agent, letting users ask natural language questions about their data and get insights back — not just query results.

## Description

This integration is a thin client for Agno's AgentOS run API. It sends a natural language query to a configured AgentOS agent, which discovers the database schema, writes and executes SQL, and interprets the results. The integration streams the agent's Server-Sent Events (SSE) response and returns the final, fully-formed answer.

Key features:
- Ask natural language questions about your data and receive interpreted insights
- Works with any Agno AgentOS deployment — the base URL, agent ID, and token are all configurable
- Parses Agno's SSE stream (`RunCompleted` / `RunContent`, including legacy `RunResponse` / `RunResponseContent` event names) with fallbacks for plain JSON or text responses
- Automatic retry with exponential backoff on transient gateway errors (HTTP 502/503/504)
- Connected-account health check against the AgentOS `/health` endpoint

## Setup & Authentication

Authentication uses custom fields pointing at your Agno AgentOS deployment.

**Authentication Type:** Custom

**Fields:**
- `api_url` (required) — Base URL of your Agno AgentOS API, including any mount prefix (e.g. `https://agno.example.com/api`)
- `api_token` (optional) — Bearer token, if your AgentOS deployment requires authentication
- `agent_id` (required) — ID of the AgentOS agent to query (e.g. `my-agent`)

## Actions

### Action: `ask_agent`

- **Description:** Ask a natural language question about your data and get insights back from the agent
- **Inputs:**
  - `query`: Natural language question about the database (required, e.g. "How many active users do we have?")
- **Outputs:**
  - `response`: The agent's answer with insights

## Requirements

- `autohive-integrations-sdk~=2.0.0`

## Usage Examples

**Ask a question about your data:**

```json
{
  "action": "ask_agent",
  "inputs": {
    "query": "How many active users do we have?"
  }
}
```

Example response:

```json
{
  "response": "There are 42 active users, up 15% from last month."
}
```

**Ask for a trend analysis:**

```json
{
  "action": "ask_agent",
  "inputs": {
    "query": "What were our top 5 products by revenue last quarter, and how did they trend month over month?"
  }
}
```

## Testing

Unit tests mock the AgentOS API and cover SSE parsing (all supported event names and framings), gateway retry behavior, credential validation, and the connected-account health check:

```bash
pytest agno-agent/ -v
```
