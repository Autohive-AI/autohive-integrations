from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from playhq.playhq import REQUEST_FAILED_MESSAGE, get_public_credentials, playhq

pytestmark = pytest.mark.unit


@pytest.fixture
def public_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "public-api-key",  # nosec B105
            "tenant": "bv",
            "region": "anz",
        },
    }
    return context


PUBLIC_ACTION_CASES = [
    (
        "list_seasons_for_organisation",
        {"organisation_id": "org-1", "cursor": "next"},
        "/v1/organisations/org-1/seasons",
        {"cursor": "next"},
        [{"id": "season-1"}],
        "seasons",
    ),
    (
        "list_teams_for_season",
        {"season_id": "season-1", "cursor": "next"},
        "/v1/seasons/season-1/teams",
        {"cursor": "next"},
        [{"id": "team-1"}],
        "teams",
    ),
    (
        "list_grades_for_season",
        {"season_id": "season-1"},
        "/v1/seasons/season-1/grades",
        None,
        [{"id": "grade-1"}],
        "grades",
    ),
    (
        "get_team_fixture",
        {"team_id": "team-1"},
        "/v1/teams/team-1/fixture",
        None,
        [{"id": "game-1"}],
        "games",
    ),
    (
        "get_grade_fixture",
        {"grade_id": "grade-1"},
        "/v2/grades/grade-1/games",
        None,
        {"rounds": [], "teams": [], "playingSurfaces": []},
        "fixture",
    ),
    (
        "get_grade_ladder",
        {"grade_id": "grade-1"},
        "/v2/grades/grade-1/ladder",
        None,
        {"entries": []},
        "ladder",
    ),
    (
        "list_grade_player_statistics",
        {"grade_id": "grade-1", "sort": "TOTAL_SCORE", "limit": 25, "cursor": "next"},
        "/v1/grades/grade-1/profiles/statistics",
        {"sort": "TOTAL_SCORE", "limit": 25, "cursor": "next"},
        {"profiles": [{"profileId": "profile-1"}]},
        "statistics",
    ),
    (
        "get_public_game_summary_v1",
        {"game_id": "game-1"},
        "/v1/games/game-1/summary",
        None,
        {"id": "game-1"},
        "summary",
    ),
    (
        "get_public_game_summary_v2",
        {"game_id": "game-1", "cursor": "next"},
        "/v2/games/game-1/summary",
        {"cursor": "next"},
        {"id": "game-1"},
        "summary",
    ),
]


class TestPublicCredentials:
    def test_reads_public_api_key_and_tenant(self, public_context):
        assert get_public_credentials(public_context) == {
            "api_key": "public-api-key",  # nosec B105
            "tenant": "bv",
            "region": "anz",
        }

    @pytest.mark.parametrize("missing", ["api_key", "tenant"])
    def test_rejects_missing_public_credentials(self, public_context, missing):
        public_context.auth["credentials"].pop(missing)

        with pytest.raises(ValueError, match=missing):
            get_public_credentials(public_context)

    async def test_public_action_defaults_to_anz_when_region_is_omitted(self, public_context):
        public_context.auth["credentials"].pop("region")
        public_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [], "metadata": {}})

        result = await playhq.execute_action(
            "list_seasons_for_organisation", {"organisation_id": "org-1"}, public_context
        )

        assert result.type == ResultType.ACTION
        assert public_context.fetch.call_args.args[0] == "https://api.playhq.com/v1/organisations/org-1/seasons"


@pytest.mark.parametrize("action,inputs,path,params,response_data,output_key", PUBLIC_ACTION_CASES)
async def test_public_action_contract_and_response(
    public_context, action, inputs, path, params, response_data, output_key
):
    public_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"data": response_data, "metadata": {"hasMore": False}},
    )

    result = await playhq.execute_action(action, inputs, public_context)

    assert result.type == ResultType.ACTION
    assert result.result.data[output_key] == response_data
    if action in {"get_public_game_summary_v1", "get_public_game_summary_v2"}:
        assert result.result.data["metadata"] == {"hasMore": False}
    request = public_context.fetch.call_args
    assert request.args[0] == f"https://api.playhq.com{path}"
    assert request.kwargs["method"] == "GET"
    assert request.kwargs["params"] == params
    assert request.kwargs["headers"]["x-api-key"] == "public-api-key"
    assert request.kwargs["headers"]["x-phq-tenant"] == "bv"


@pytest.mark.parametrize("action,inputs,path,params,response_data,output_key", PUBLIC_ACTION_CASES)
async def test_public_action_returns_action_error(
    public_context, action, inputs, path, params, response_data, output_key
):
    public_context.fetch.side_effect = RuntimeError("public API unavailable")

    result = await playhq.execute_action(action, inputs, public_context)

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == REQUEST_FAILED_MESSAGE


@pytest.mark.parametrize("action,inputs,path,params,response_data,output_key", PUBLIC_ACTION_CASES)
async def test_public_action_validates_required_identifier(
    public_context, action, inputs, path, params, response_data, output_key
):
    invalid_inputs = dict(inputs)
    invalid_inputs.pop(next(iter(invalid_inputs)))

    result = await playhq.execute_action(action, invalid_inputs, public_context)

    assert result.type == ResultType.VALIDATION_ERROR
    public_context.fetch.assert_not_awaited()


async def test_grade_ladder_preserves_documented_root_object(public_context):
    public_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"gradeId": "grade-1", "ladders": []},
    )

    result = await playhq.execute_action("get_grade_ladder", {"grade_id": "grade-1"}, public_context)

    assert result.result.data["ladder"] == {"gradeId": "grade-1", "ladders": []}


async def test_grade_fixture_preserves_documented_root_object(public_context):
    fixture = {"rounds": [], "teams": [], "playingSurfaces": []}
    public_context.fetch.return_value = FetchResponse(status=200, headers={}, data=fixture)

    result = await playhq.execute_action("get_grade_fixture", {"grade_id": "grade-1"}, public_context)

    assert result.result.data["fixture"] == fixture


@pytest.mark.parametrize("action", ["get_public_game_summary_v1", "get_public_game_summary_v2"])
async def test_public_summary_preserves_pagination_cursor(public_context, action):
    public_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "data": {"id": "game-1"},
            "metadata": {"hasMore": True, "nextCursor": "next-summary-page"},
        },
    )

    result = await playhq.execute_action(action, {"game_id": "game-1"}, public_context)

    assert result.result.data == {
        "summary": {"id": "game-1"},
        "metadata": {"hasMore": True, "nextCursor": "next-summary-page"},
    }
