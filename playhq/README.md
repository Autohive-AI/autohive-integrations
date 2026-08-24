# PlayHQ

Access the complete non-deprecated REST surface currently published in the [PlayHQ API reference](https://docs.playhq.com/tech/api/playhq-external-api): 27 actions across organisations, seasons, teams, grades, games, profiles, webhook filters, payment contracts, and referees.

## Authentication

PlayHQ publishes two authentication schemes, both configured through this integration's custom credentials:

- **Private Partner API** — requires a formal PlayHQ partner agreement. The integration exchanges the supplied client ID and secret for a short-lived JWT and never exposes that JWT in action output.
- **Public API** — uses a PlayHQ API key and tenant code in the `x-api-key` and `x-phq-tenant` headers.

Configure:

- **Client ID** — Partner API client ID supplied by PlayHQ.
- **Client Secret** — Partner API client secret supplied by PlayHQ.
- **Public API Key** — API key for public endpoints; optional when only private actions are used.
- **Public API Tenant** — Tenant code such as `bv`, `afl`, or `ca`; optional when only private actions are used.
- **Region** — `anz` (Australia/New Zealand), `europe`, or `canada`.

At least one complete credential pair is required when connecting an account: Client ID with Client Secret for private actions, or Public API Key with Public API Tenant for public actions. You may provide both pairs to use every action from one account.

Private endpoints may return data that is hidden from PlayHQ's public site. Treat action output as private partner data and follow the data-use terms in your PlayHQ agreement.

## Actions

### Organisations and competition hierarchy

- `list_organisations` — private v2 organisation listing with filters and cursor pagination.
- `list_seasons_for_organisation` — public competition seasons for an association.
- `list_teams_for_organisation` — private teams beneath an association.
- `list_teams_for_season` — public teams participating in a season.
- `list_grades_for_season` — public grades beneath a season.

### Fixtures, ladders, and statistics

- `get_team_fixture` — public team fixture; not currently applicable to cricket.
- `get_grade_fixture` — current public v2 grade fixture.
- `get_grade_ladder` — current public v2 grade ladder.
- `list_grade_player_statistics` — public player statistics for a grade; not currently applicable to cricket.
- `list_games_for_organisation` — private v2 games within an inclusive date range.
- `list_games_for_organisation_on_date` — private v1 games on one date.

### Game details and referee access

- `get_game_summary` — private v2 summary.
- `get_private_game_summary_v1` — private v1 summary for territory-based sports.
- `get_public_game_summary_v1` — public v1 summary for territory-based sports.
- `get_public_game_summary_v2` — public v2 summary.
- `get_game_events` — private electronic-scoring events; not currently applicable to cricket.
- `get_game_signed_url` — generates a time-limited referee resource URL.
- `set_game_live_streaming` — enables or disables live streaming for a game.

### Profiles

- `list_profile_dependants` — private tenant-visible profile dependants.
- `get_profile_career_statistics` — private career statistics by optional role.
- `list_profile_statistic_seasons` — private seasons in which a profile earned statistics.
- `get_profile_season_statistics` — private profile statistics for one season.

### Webhooks and partner administration

- `list_webhook_filter_entity_ids` — lists IDs on a subscription filter.
- `add_webhook_filter_entity_id` — adds an ID and changes webhook delivery.
- `remove_webhook_filter_entity_id` — removes an ID and changes webhook delivery.
- `set_game_payment_contract` — activates or deactivates an organisation contract.
- `link_referee_profile` — creates a one-time external-referee/profile mapping.

Deprecated PlayHQ endpoints are intentionally excluded when a current replacement exists. Webhook `EVENT` definitions are incoming payload contracts rather than callable endpoints, so they are not actions.

## Pagination

Paginated list and public game-summary actions return one page at a time. When `metadata.hasMore` is true, pass `metadata.nextCursor` as the next call's `cursor`.

## Testing

Install dependencies and run the mocked unit suite:

```bash
uv pip install -r playhq/requirements.txt
pytest playhq/ -v
```

For live read-only tests, set the PlayHQ variables documented in the repository root `.env.example`, then run:

```bash
pytest playhq/tests/test_playhq_integration.py -m "integration and not destructive"
```

Live tests skip individual actions when their required resource IDs are not configured.

Mutation tests change live-streaming settings, webhook filters, payment contracts, or referee mappings. Run them only against disposable or deliberately selected resources:

```bash
pytest playhq/tests/test_playhq_integration.py -m "integration and destructive"
```

The webhook test adds and then removes its configured entity ID. The other PlayHQ write endpoints do not expose a reliable read/restore operation, so their test values must be chosen with care. Referee linking is a one-time mapping and may not be reversible.

## Troubleshooting

- **400/403 during authentication** — verify the client ID, client secret, and selected region.
- **Missing public credentials** — public actions require both the API key and tenant code; private client credentials do not substitute for them.
- **403 from a private endpoint** — confirm the resource belongs to the organisation scope granted in the PlayHQ partner agreement.
- **Missing results** — continue with `metadata.nextCursor` while `metadata.hasMore` is true.
- **Unsupported game data** — check the endpoint's territory-sport limitations in the official API documentation.

## Official resources

- [PlayHQ API documentation](https://docs.playhq.com/tech/)
- [Generate auth token](https://docs.playhq.com/tech/api/generate-auth-token)
- [PlayHQ API usage guide](https://support.playhq.com/hc/en-us/articles/23949453276572-How-To-Use-PlayHQ-API-s)
