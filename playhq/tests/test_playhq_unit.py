from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from playhq.playhq import REQUEST_FAILED_MESSAGE, PlayHQClient, get_credentials, path_identifier, playhq

pytestmark = pytest.mark.unit

TOKEN = "test-access-token"  # nosec B105
ORGANISATION_ID = "11111111-2222-3333-4444-555555555555"
GAME_ID = "game-123"


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
            "region": "anz",
        },
    }
    return context


def queue_success(context, data, metadata=None):
    context.fetch.side_effect = [
        FetchResponse(status=201, headers={}, data={"access_token": TOKEN, "exp": 9999999999}),
        FetchResponse(status=200, headers={}, data={"data": data, "metadata": metadata or {}}),
    ]


class TestCredentials:
    def test_accepts_flat_custom_auth(self, mock_context):
        mock_context.auth = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
            "region": "anz",
        }
        credentials = get_credentials(mock_context)

        assert credentials == {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
            "region": "anz",
        }

    def test_accepts_wrapped_runtime_auth(self, mock_context):
        mock_context.auth = {
            "credentials": {
                "client_id": "wrapped-id",
                "client_secret": "wrapped-secret",  # nosec B105
                "region": "canada",
            }
        }

        credentials = get_credentials(mock_context)

        assert credentials["client_id"] == "wrapped-id"
        assert credentials["region"] == "canada"

    @pytest.mark.parametrize("missing", ["client_id", "client_secret"])
    def test_rejects_missing_required_credentials(self, mock_context, missing):
        mock_context.auth["credentials"].pop(missing)

        with pytest.raises(ValueError, match=missing):
            get_credentials(mock_context)

    def test_path_identifier_encodes_path_separators(self):
        assert path_identifier("game/with spaces") == "game%2Fwith%20spaces"

    def test_rejects_unsupported_region(self, mock_context):
        mock_context.auth["credentials"]["region"] = "unknown"

        with pytest.raises(ValueError, match="Unsupported PlayHQ region"):
            get_credentials(mock_context)

    @pytest.mark.parametrize(
        "credentials",
        [
            {},
            {"client_id": "test-client-id"},
            {"client_secret": "test-client-secret"},  # nosec B105
            {"api_key": "test-api-key"},  # nosec B105
            {"tenant": "bv"},
            {"client_id": "", "client_secret": "test-client-secret"},  # nosec B105
        ],
    )
    async def test_sdk_rejects_incomplete_credential_pairs(self, mock_context, credentials):
        mock_context.auth = {"auth_type": "Custom", "credentials": credentials}

        result = await playhq.execute_action("list_organisations", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    async def test_sdk_accepts_both_complete_credential_pairs(self, mock_context):
        mock_context.auth["credentials"].update({"api_key": "test-api-key", "tenant": "bv"})  # nosec B105
        queue_success(mock_context, {"organisations": []})

        result = await playhq.execute_action("list_organisations", {}, mock_context)

        assert result.type == ResultType.ACTION


class TestPlayHQClient:
    async def test_authentication_request_contract(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201, headers={}, data={"access_token": TOKEN, "exp": 9999999999}
        )

        token = await PlayHQClient(mock_context).get_access_token()

        assert token == TOKEN
        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.playhq.com/auth"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"clientId": "test-client-id", "clientSecret": "test-client-secret"}

    async def test_uses_region_specific_base_url(self, mock_context):
        mock_context.auth["credentials"]["region"] = "europe"
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"access_token": TOKEN})

        await PlayHQClient(mock_context).get_access_token()

        assert mock_context.fetch.call_args.args[0] == "https://api.euprod.playhq.com/auth"

    async def test_caches_token_within_client(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"access_token": TOKEN})
        client = PlayHQClient(mock_context)

        assert await client.get_access_token() == TOKEN
        assert await client.get_access_token() == TOKEN

        mock_context.fetch.assert_awaited_once()

    async def test_rejects_auth_response_without_token(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"exp": 9999999999})

        with pytest.raises(ValueError, match="access_token"):
            await PlayHQClient(mock_context).get_access_token()


class TestListOrganisations:
    async def test_returns_organisations_and_metadata(self, mock_context):
        queue_success(
            mock_context,
            {"organisations": [{"id": ORGANISATION_ID, "name": "Example Association"}]},
            {"hasMore": False},
        )

        result = await playhq.execute_action("list_organisations", {}, mock_context)

        assert result.result.data["organisations"][0]["id"] == ORGANISATION_ID
        assert result.result.data["metadata"] == {"hasMore": False}

    async def test_sends_default_filters(self, mock_context):
        queue_success(mock_context, {"organisations": []})

        await playhq.execute_action("list_organisations", {}, mock_context)

        request = mock_context.fetch.call_args_list[1]
        assert request.args[0] == "https://api.playhq.com/partner/v2/organisations"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["params"] == {"limit": 10, "type": "ALL"}
        assert request.kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"

    async def test_sends_cursor_limit_and_type(self, mock_context):
        queue_success(mock_context, {"organisations": []})

        await playhq.execute_action(
            "list_organisations",
            {"cursor": "next-page", "limit": 50, "type": "CLUB"},
            mock_context,
        )

        params = mock_context.fetch.call_args_list[1].kwargs["params"]
        assert params == {"cursor": "next-page", "limit": 50, "type": "CLUB"}

    async def test_authentication_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("authentication unavailable")

        result = await playhq.execute_action("list_organisations", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == REQUEST_FAILED_MESSAGE


class TestListTeamsForOrganisation:
    async def test_returns_teams_and_metadata(self, mock_context):
        queue_success(mock_context, [{"id": "team-1", "name": "Falcons"}], {"nextCursor": "next"})

        result = await playhq.execute_action(
            "list_teams_for_organisation", {"organisation_id": ORGANISATION_ID}, mock_context
        )

        assert result.result.data["teams"][0]["name"] == "Falcons"
        assert result.result.data["metadata"]["nextCursor"] == "next"

    async def test_request_url_and_method(self, mock_context):
        queue_success(mock_context, [])

        await playhq.execute_action("list_teams_for_organisation", {"organisation_id": ORGANISATION_ID}, mock_context)

        request = mock_context.fetch.call_args_list[1]
        assert request.args[0] == f"https://api.playhq.com/partner/v1/organisations/{ORGANISATION_ID}/teams"
        assert request.kwargs["method"] == "GET"

    async def test_sends_cursor_when_provided(self, mock_context):
        queue_success(mock_context, [])

        await playhq.execute_action(
            "list_teams_for_organisation",
            {"organisation_id": ORGANISATION_ID, "cursor": "teams-page-2"},
            mock_context,
        )

        assert mock_context.fetch.call_args_list[1].kwargs["params"] == {"cursor": "teams-page-2"}

    async def test_api_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
            Exception("teams endpoint failed"),
        ]

        result = await playhq.execute_action(
            "list_teams_for_organisation", {"organisation_id": ORGANISATION_ID}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == REQUEST_FAILED_MESSAGE


class TestListGamesForOrganisation:
    def inputs(self, **overrides):
        values = {
            "organisation_id": ORGANISATION_ID,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        }
        values.update(overrides)
        return values

    async def test_returns_games_and_metadata(self, mock_context):
        queue_success(mock_context, [{"id": GAME_ID}], {"hasMore": False})

        result = await playhq.execute_action("list_games_for_organisation", self.inputs(), mock_context)

        assert result.result.data == {"games": [{"id": GAME_ID}], "metadata": {"hasMore": False}}

    async def test_request_contract_and_defaults(self, mock_context):
        queue_success(mock_context, [])

        await playhq.execute_action("list_games_for_organisation", self.inputs(), mock_context)

        request = mock_context.fetch.call_args_list[1]
        assert request.args[0] == f"https://api.playhq.com/partner/v2/organisations/{ORGANISATION_ID}/games"
        assert request.kwargs["params"] == {
            "limit": 10,
            "startDate": "2026-08-01",
            "endDate": "2026-08-31",
            "visibility": "all",
        }

    async def test_sends_optional_filters(self, mock_context):
        queue_success(mock_context, [])

        await playhq.execute_action(
            "list_games_for_organisation",
            self.inputs(cursor="games-page-2", limit=100, visibility="visible"),
            mock_context,
        )

        params = mock_context.fetch.call_args_list[1].kwargs["params"]
        assert params["cursor"] == "games-page-2"
        assert params["limit"] == 100
        assert params["visibility"] == "visible"

    async def test_rejects_reversed_date_range_without_fetch(self, mock_context):
        result = await playhq.execute_action(
            "list_games_for_organisation",
            self.inputs(start_date="2026-09-01", end_date="2026-08-31"),
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == REQUEST_FAILED_MESSAGE
        mock_context.fetch.assert_not_awaited()

    async def test_rejects_invalid_calendar_date_without_fetch(self, mock_context):
        result = await playhq.execute_action(
            "list_games_for_organisation", self.inputs(start_date="2026-02-30"), mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()


class TestGetGameSummary:
    async def test_returns_summary(self, mock_context):
        queue_success(mock_context, {"id": GAME_ID, "status": "FINAL"})

        result = await playhq.execute_action("get_game_summary", {"game_id": GAME_ID}, mock_context)

        assert result.result.data["summary"]["status"] == "FINAL"

    async def test_request_url_and_auth_header(self, mock_context):
        queue_success(mock_context, {})

        await playhq.execute_action("get_game_summary", {"game_id": GAME_ID}, mock_context)

        request = mock_context.fetch.call_args_list[1]
        assert request.args[0] == f"https://api.playhq.com/partner/v2/games/{GAME_ID}/summary"
        assert request.kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"

    async def test_empty_data_returns_empty_summary(self, mock_context):
        queue_success(mock_context, {})

        result = await playhq.execute_action("get_game_summary", {"game_id": GAME_ID}, mock_context)

        assert result.result.data == {"summary": {}}

    async def test_non_object_response_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        result = await playhq.execute_action("get_game_summary", {"game_id": GAME_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == REQUEST_FAILED_MESSAGE


class TestGetGameEvents:
    async def test_returns_events(self, mock_context):
        queue_success(mock_context, {"events": [{"type": "SCORE"}]})

        result = await playhq.execute_action("get_game_events", {"game_id": GAME_ID}, mock_context)

        assert result.result.data["events"]["events"][0]["type"] == "SCORE"

    async def test_request_url_and_method(self, mock_context):
        queue_success(mock_context, {})

        await playhq.execute_action("get_game_events", {"game_id": GAME_ID}, mock_context)

        request = mock_context.fetch.call_args_list[1]
        assert request.args[0] == f"https://api.playhq.com/partner/v1/games/{GAME_ID}/events"
        assert request.kwargs["method"] == "GET"

    async def test_empty_data_returns_empty_events(self, mock_context):
        queue_success(mock_context, {})

        result = await playhq.execute_action("get_game_events", {"game_id": GAME_ID}, mock_context)

        assert result.result.data == {"events": {}}

    async def test_api_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
            Exception("events not available"),
        ]

        result = await playhq.execute_action("get_game_events", {"game_id": GAME_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == REQUEST_FAILED_MESSAGE
