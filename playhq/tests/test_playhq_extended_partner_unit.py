from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from playhq.playhq import REQUEST_FAILED_MESSAGE, playhq

pytestmark = pytest.mark.unit

TOKEN = "partner-access-token"  # nosec B105


@pytest.fixture
def partner_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "client_id": "partner-id",
            "client_secret": "partner-secret",  # nosec B105
            "region": "anz",
        },
    }
    return context


PARTNER_ACTION_CASES = [
    (
        "get_private_game_summary_v1",
        {"game_id": "game-1"},
        "GET",
        "/partner/v1/games/game-1/summary",
        None,
        {"id": "game-1"},
        "summary",
    ),
    (
        "set_game_live_streaming",
        {"game_id": "game-1", "enabled": True},
        "PUT",
        "/partner/v1/games/game-1/live-streaming",
        {"liveStreamingEnabled": True},
        {"updated": True},
        "result",
    ),
    (
        "get_game_signed_url",
        {"game_id": "game-1", "first_name": "Ari", "last_name": "Lee", "user_id": "ref-1"},
        "POST",
        "/partner/v1/games/game-1/get-signed-url",
        {"firstName": "Ari", "lastName": "Lee", "userId": "ref-1"},
        {"url": "https://signed.example"},
        "signed_url",
    ),
    (
        "list_games_for_organisation_on_date",
        {"organisation_id": "org-1", "date": "2026-08-24", "cursor": "next"},
        "GET",
        "/partner/v1/organisations/org-1/games/2026-08-24",
        None,
        [{"id": "game-1"}],
        "games",
    ),
    (
        "list_profile_dependants",
        {"profile_id": "profile-1"},
        "GET",
        "/partner/v1/profiles/profile-1/dependants",
        None,
        [{"id": "profile-2"}],
        "dependants",
    ),
    (
        "get_profile_career_statistics",
        {"profile_id": "profile-1", "role": "PLAYER"},
        "GET",
        "/partner/v1/profiles/profile-1/statistics/career",
        None,
        {"totals": {}},
        "statistics",
    ),
    (
        "list_profile_statistic_seasons",
        {"profile_id": "profile-1", "role": "PLAYER"},
        "GET",
        "/partner/v1/profiles/profile-1/statistics/seasons",
        None,
        [{"id": "season-1"}],
        "seasons",
    ),
    (
        "get_profile_season_statistics",
        {"profile_id": "profile-1", "season_id": "season-1", "role": "PLAYER"},
        "GET",
        "/partner/v1/profiles/profile-1/statistics/seasons/season-1",
        None,
        {"totals": {}},
        "statistics",
    ),
    (
        "list_webhook_filter_entity_ids",
        {"subscriber_id": "sub-1", "subscription_id": "subscription-1", "entity": "GAME"},
        "GET",
        "/partner/v1/webhooks/subscribers/sub-1/subscriptions/subscription-1/filters/GAME/ids",
        None,
        ["game-1"],
        "entity_ids",
    ),
    (
        "add_webhook_filter_entity_id",
        {
            "subscriber_id": "sub-1",
            "subscription_id": "subscription-1",
            "entity": "GAME",
            "entity_id": "game-1",
        },
        "PUT",
        "/partner/v1/webhooks/subscribers/sub-1/subscriptions/subscription-1/filters/GAME/ids/game-1",
        None,
        {"updated": True},
        "result",
    ),
    (
        "remove_webhook_filter_entity_id",
        {
            "subscriber_id": "sub-1",
            "subscription_id": "subscription-1",
            "entity": "GAME",
            "entity_id": "game-1",
        },
        "DELETE",
        "/partner/v1/webhooks/subscribers/sub-1/subscriptions/subscription-1/filters/GAME/ids/game-1",
        None,
        {"updated": True},
        "result",
    ),
    (
        "set_game_payment_contract",
        {"organisation_id": "org-1", "status": "ACTIVE"},
        "PUT",
        "/partner/v1/organisations/org-1/game-payment-contracts",
        {"status": "ACTIVE"},
        {"updated": True},
        "result",
    ),
    (
        "link_referee_profile",
        {"provider": "Example Association", "external_user_id": "ref-1", "profile_id": "profile-1"},
        "POST",
        "/partner/v1/referees/link",
        {"provider": "Example Association", "externalUserId": "ref-1", "profileId": "profile-1"},
        {"linked": True},
        "result",
    ),
]


def queue_partner_success(context, response_data):
    context.fetch.side_effect = [
        FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
        FetchResponse(status=200, headers={}, data={"data": response_data, "metadata": {"hasMore": False}}),
    ]


@pytest.mark.parametrize("action,inputs,method,path,body,response_data,output_key", PARTNER_ACTION_CASES)
async def test_extended_partner_action_contract_and_response(
    partner_context, action, inputs, method, path, body, response_data, output_key
):
    queue_partner_success(partner_context, response_data)

    result = await playhq.execute_action(action, inputs, partner_context)

    assert result.type == ResultType.ACTION
    assert result.result.data[output_key] == response_data
    request = partner_context.fetch.call_args_list[1]
    assert request.args[0] == f"https://api.playhq.com{path}"
    assert request.kwargs["method"] == method
    assert request.kwargs["json"] == body
    assert request.kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("action,inputs,method,path,body,response_data,output_key", PARTNER_ACTION_CASES)
async def test_extended_partner_action_returns_action_error(
    partner_context, action, inputs, method, path, body, response_data, output_key
):
    partner_context.fetch.side_effect = RuntimeError("partner API unavailable")

    result = await playhq.execute_action(action, inputs, partner_context)

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == REQUEST_FAILED_MESSAGE


@pytest.mark.parametrize("action,inputs,method,path,body,response_data,output_key", PARTNER_ACTION_CASES)
async def test_extended_partner_action_validates_required_input(
    partner_context, action, inputs, method, path, body, response_data, output_key
):
    invalid_inputs = dict(inputs)
    invalid_inputs.pop(next(iter(invalid_inputs)))

    result = await playhq.execute_action(action, invalid_inputs, partner_context)

    assert result.type == ResultType.VALIDATION_ERROR
    partner_context.fetch.assert_not_awaited()


async def test_games_on_date_rejects_invalid_date_without_fetch(partner_context):
    result = await playhq.execute_action(
        "list_games_for_organisation_on_date",
        {"organisation_id": "org-1", "date": "2026-02-30"},
        partner_context,
    )

    assert result.type == ResultType.ACTION_ERROR
    partner_context.fetch.assert_not_awaited()


async def test_games_on_date_sends_cursor(partner_context):
    queue_partner_success(partner_context, [])

    await playhq.execute_action(
        "list_games_for_organisation_on_date",
        {"organisation_id": "org-1", "date": "2026-08-24", "cursor": "next"},
        partner_context,
    )

    assert partner_context.fetch.call_args_list[1].kwargs["params"] == {"cursor": "next"}


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("get_profile_career_statistics", {"profile_id": "profile-1", "role": "COACH"}),
        ("list_profile_statistic_seasons", {"profile_id": "profile-1", "role": "COACH"}),
        (
            "get_profile_season_statistics",
            {"profile_id": "profile-1", "season_id": "season-1", "role": "COACH"},
        ),
    ],
)
async def test_profile_statistics_sends_role(partner_context, action, inputs):
    queue_partner_success(partner_context, {})

    await playhq.execute_action(action, inputs, partner_context)

    assert partner_context.fetch.call_args_list[1].kwargs["params"] == {"role": "COACH"}


async def test_profile_dependants_unwraps_documented_named_root(partner_context):
    partner_context.fetch.side_effect = [
        FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
        FetchResponse(status=200, headers={}, data={"dependants": [{"id": "profile-2"}]}),
    ]

    result = await playhq.execute_action("list_profile_dependants", {"profile_id": "profile-1"}, partner_context)

    assert result.result.data["dependants"] == [{"id": "profile-2"}]


async def test_webhook_filter_ids_accepts_documented_root_array(partner_context):
    partner_context.fetch.side_effect = [
        FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
        FetchResponse(status=200, headers={}, data=["game-1", "game-2"]),
    ]

    result = await playhq.execute_action(
        "list_webhook_filter_entity_ids",
        {"subscriber_id": "sub-1", "subscription_id": "subscription-1", "entity": "GAME"},
        partner_context,
    )

    assert result.result.data["entity_ids"] == ["game-1", "game-2"]


async def test_profile_season_statistics_preserves_complete_root_record(partner_context):
    record = {"season": {"id": "season-1"}, "role": "PLAYER", "statistics": []}
    partner_context.fetch.side_effect = [
        FetchResponse(status=201, headers={}, data={"access_token": TOKEN}),
        FetchResponse(status=200, headers={}, data=record),
    ]

    result = await playhq.execute_action(
        "get_profile_season_statistics",
        {"profile_id": "profile-1", "season_id": "season-1"},
        partner_context,
    )

    assert result.result.data["statistics"] == record
