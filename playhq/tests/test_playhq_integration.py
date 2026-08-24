"""Live, read-only integration tests for the PlayHQ Partner API.

Run safely with:
    pytest playhq/tests/test_playhq_integration.py -m "integration and not destructive"

These tests are excluded from default pytest discovery and skip when the
required PlayHQ credentials or resource IDs are not configured.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse

from playhq.playhq import playhq

pytestmark = pytest.mark.integration


def build_live_context(credentials):
    import aiohttp
    import json as json_module

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as response:
                body = await response.read()
                try:
                    data = json_module.loads(body) if body else None
                except (TypeError, ValueError):
                    data = None
                if response.status >= 400:
                    raise RuntimeError(f"PlayHQ returned HTTP {response.status}")
                return FetchResponse(status=response.status, headers=dict(response.headers), data=data)

    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(side_effect=real_fetch)
    context.auth = {
        "auth_type": "Custom",
        "credentials": credentials,
    }
    return context


@pytest.fixture
def live_context(env_credentials):
    client_id = env_credentials("PLAYHQ_CLIENT_ID")
    client_secret = env_credentials("PLAYHQ_CLIENT_SECRET")
    region = env_credentials("PLAYHQ_REGION") or "anz"
    if not client_id or not client_secret:
        pytest.skip("PLAYHQ_CLIENT_ID and PLAYHQ_CLIENT_SECRET are required")
    return build_live_context({"client_id": client_id, "client_secret": client_secret, "region": region})


@pytest.fixture
def public_live_context(env_credentials):
    api_key = env_credentials("PLAYHQ_API_KEY")
    tenant = env_credentials("PLAYHQ_TENANT")
    region = env_credentials("PLAYHQ_REGION") or "anz"
    if not api_key or not tenant:
        pytest.skip("PLAYHQ_API_KEY and PLAYHQ_TENANT are required")
    return build_live_context({"api_key": api_key, "tenant": tenant, "region": region})


def require_resource(env_credentials, name):
    value = env_credentials(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


class TestListOrganisations:
    async def test_returns_paginated_organisations(self, live_context):
        result = await playhq.execute_action("list_organisations", {"limit": 2}, live_context)

        data = result.result.data
        assert isinstance(data["organisations"], list)
        assert "metadata" in data

    async def test_respects_type_filter(self, live_context):
        result = await playhq.execute_action("list_organisations", {"limit": 2, "type": "ASSOCIATION"}, live_context)

        assert isinstance(result.result.data["organisations"], list)


class TestListTeamsForOrganisation:
    async def test_returns_teams(self, live_context, env_credentials):
        organisation_id = require_resource(env_credentials, "PLAYHQ_TEST_ORGANISATION_ID")

        result = await playhq.execute_action(
            "list_teams_for_organisation", {"organisation_id": organisation_id}, live_context
        )

        assert "teams" in result.result.data
        assert "metadata" in result.result.data


class TestListGamesForOrganisation:
    async def test_returns_games_for_date_range(self, live_context, env_credentials):
        organisation_id = require_resource(env_credentials, "PLAYHQ_TEST_ORGANISATION_ID")
        today = date.today().isoformat()

        result = await playhq.execute_action(
            "list_games_for_organisation",
            {"organisation_id": organisation_id, "start_date": today, "end_date": today, "limit": 2},
            live_context,
        )

        assert "games" in result.result.data
        assert "metadata" in result.result.data


class TestGetGameSummary:
    async def test_returns_game_summary(self, live_context, env_credentials):
        game_id = require_resource(env_credentials, "PLAYHQ_TEST_GAME_ID")

        result = await playhq.execute_action("get_game_summary", {"game_id": game_id}, live_context)

        assert "summary" in result.result.data
        assert isinstance(result.result.data["summary"], dict)


# ---- Public API-key endpoints ----


PUBLIC_READ_CASES = [
    ("list_seasons_for_organisation", "PLAYHQ_TEST_ORGANISATION_ID", "organisation_id", "seasons"),
    ("list_teams_for_season", "PLAYHQ_TEST_SEASON_ID", "season_id", "teams"),
    ("list_grades_for_season", "PLAYHQ_TEST_SEASON_ID", "season_id", "grades"),
    ("get_team_fixture", "PLAYHQ_TEST_TEAM_ID", "team_id", "games"),
    ("get_grade_fixture", "PLAYHQ_TEST_GRADE_ID", "grade_id", "fixture"),
    ("get_grade_ladder", "PLAYHQ_TEST_GRADE_ID", "grade_id", "ladder"),
    ("list_grade_player_statistics", "PLAYHQ_TEST_GRADE_ID", "grade_id", "statistics"),
    ("get_public_game_summary_v1", "PLAYHQ_TEST_GAME_ID", "game_id", "summary"),
    ("get_public_game_summary_v2", "PLAYHQ_TEST_GAME_ID", "game_id", "summary"),
]


@pytest.mark.parametrize("action,resource_variable,input_key,output_key", PUBLIC_READ_CASES)
async def test_public_endpoint_returns_documented_output(
    public_live_context,
    env_credentials,
    action,
    resource_variable,
    input_key,
    output_key,
):
    resource_id = require_resource(env_credentials, resource_variable)

    result = await playhq.execute_action(action, {input_key: resource_id}, public_live_context)

    assert output_key in result.result.data
    if action in {"get_public_game_summary_v1", "get_public_game_summary_v2"}:
        assert isinstance(result.result.data["metadata"], dict)


# ---- Extended private read-only endpoints ----


class TestExtendedPrivateGames:
    async def test_returns_v1_summary(self, live_context, env_credentials):
        game_id = require_resource(env_credentials, "PLAYHQ_TEST_GAME_ID")

        result = await playhq.execute_action("get_private_game_summary_v1", {"game_id": game_id}, live_context)

        assert "summary" in result.result.data

    async def test_returns_games_on_date(self, live_context, env_credentials):
        organisation_id = require_resource(env_credentials, "PLAYHQ_TEST_ORGANISATION_ID")

        result = await playhq.execute_action(
            "list_games_for_organisation_on_date",
            {"organisation_id": organisation_id, "date": date.today().isoformat()},
            live_context,
        )

        assert "games" in result.result.data
        assert "metadata" in result.result.data

    async def test_returns_signed_referee_url(self, live_context, env_credentials):
        game_id = require_resource(env_credentials, "PLAYHQ_TEST_GAME_ID")
        first_name = require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_FIRST_NAME")
        last_name = require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_LAST_NAME")
        user_id = require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_EXTERNAL_USER_ID")

        result = await playhq.execute_action(
            "get_game_signed_url",
            {"game_id": game_id, "first_name": first_name, "last_name": last_name, "user_id": user_id},
            live_context,
        )

        assert "signed_url" in result.result.data


class TestPrivateProfiles:
    async def test_returns_dependants(self, live_context, env_credentials):
        profile_id = require_resource(env_credentials, "PLAYHQ_TEST_PROFILE_ID")

        result = await playhq.execute_action("list_profile_dependants", {"profile_id": profile_id}, live_context)

        assert "dependants" in result.result.data

    @pytest.mark.parametrize(
        "action,extra_inputs,output_key",
        [
            ("get_profile_career_statistics", {}, "statistics"),
            ("list_profile_statistic_seasons", {}, "seasons"),
            (
                "get_profile_season_statistics",
                {"season_id_variable": "PLAYHQ_TEST_SEASON_ID"},
                "statistics",
            ),
        ],
    )
    async def test_returns_profile_statistics(self, live_context, env_credentials, action, extra_inputs, output_key):
        inputs = {"profile_id": require_resource(env_credentials, "PLAYHQ_TEST_PROFILE_ID")}
        if extra_inputs.get("season_id_variable"):
            inputs["season_id"] = require_resource(env_credentials, extra_inputs["season_id_variable"])

        result = await playhq.execute_action(action, inputs, live_context)

        assert output_key in result.result.data


class TestWebhookFilters:
    async def test_lists_entity_ids(self, live_context, env_credentials):
        inputs = {
            "subscriber_id": require_resource(env_credentials, "PLAYHQ_TEST_SUBSCRIBER_ID"),
            "subscription_id": require_resource(env_credentials, "PLAYHQ_TEST_SUBSCRIPTION_ID"),
            "entity": env_credentials("PLAYHQ_TEST_FILTER_ENTITY") or "GAME",
        }

        result = await playhq.execute_action("list_webhook_filter_entity_ids", inputs, live_context)

        assert isinstance(result.result.data["entity_ids"], list)


# ---- Destructive private endpoint tests ----
# Run only with: pytest playhq/tests/test_playhq_integration.py -m "integration and destructive"


@pytest.mark.destructive
class TestPrivateMutations:
    async def test_sets_live_streaming(self, live_context, env_credentials):
        game_id = require_resource(env_credentials, "PLAYHQ_TEST_GAME_ID")
        enabled_value = require_resource(env_credentials, "PLAYHQ_TEST_LIVE_STREAMING_ENABLED")
        if enabled_value.lower() not in {"true", "false"}:
            pytest.skip("PLAYHQ_TEST_LIVE_STREAMING_ENABLED must be true or false")

        result = await playhq.execute_action(
            "set_game_live_streaming",
            {"game_id": game_id, "enabled": enabled_value.lower() == "true"},
            live_context,
        )

        assert "result" in result.result.data

    async def test_webhook_filter_add_remove_lifecycle(self, live_context, env_credentials):
        inputs = {
            "subscriber_id": require_resource(env_credentials, "PLAYHQ_TEST_SUBSCRIBER_ID"),
            "subscription_id": require_resource(env_credentials, "PLAYHQ_TEST_SUBSCRIPTION_ID"),
            "entity": env_credentials("PLAYHQ_TEST_FILTER_ENTITY") or "GAME",
            "entity_id": require_resource(env_credentials, "PLAYHQ_TEST_FILTER_ENTITY_ID"),
        }

        current_result = await playhq.execute_action(
            "list_webhook_filter_entity_ids",
            {name: inputs[name] for name in ("subscriber_id", "subscription_id", "entity")},
            live_context,
        )
        if inputs["entity_id"] in current_result.result.data["entity_ids"]:
            pytest.skip("PLAYHQ_TEST_FILTER_ENTITY_ID is already configured; use a disposable absent ID")

        add_attempted = False
        try:
            add_attempted = True
            add_result = await playhq.execute_action("add_webhook_filter_entity_id", inputs, live_context)
            confirmed_result = await playhq.execute_action(
                "list_webhook_filter_entity_ids",
                {name: inputs[name] for name in ("subscriber_id", "subscription_id", "entity")},
                live_context,
            )
            assert "result" in add_result.result.data
            assert inputs["entity_id"] in confirmed_result.result.data["entity_ids"]
        finally:
            if add_attempted:
                remove_result = await playhq.execute_action("remove_webhook_filter_entity_id", inputs, live_context)
                assert "result" in remove_result.result.data
                restored_result = await playhq.execute_action(
                    "list_webhook_filter_entity_ids",
                    {name: inputs[name] for name in ("subscriber_id", "subscription_id", "entity")},
                    live_context,
                )
                assert inputs["entity_id"] not in restored_result.result.data["entity_ids"]

    async def test_sets_game_payment_contract(self, live_context, env_credentials):
        organisation_id = require_resource(env_credentials, "PLAYHQ_TEST_ORGANISATION_ID")
        status = require_resource(env_credentials, "PLAYHQ_TEST_PAYMENT_CONTRACT_STATUS")

        result = await playhq.execute_action(
            "set_game_payment_contract",
            {"organisation_id": organisation_id, "status": status},
            live_context,
        )

        assert "result" in result.result.data

    async def test_links_referee_profile(self, live_context, env_credentials):
        inputs = {
            "provider": require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_PROVIDER"),
            "external_user_id": require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_EXTERNAL_USER_ID"),
            "profile_id": require_resource(env_credentials, "PLAYHQ_TEST_REFEREE_PROFILE_ID"),
        }

        result = await playhq.execute_action("link_referee_profile", inputs, live_context)

        assert "result" in result.result.data


class TestGetGameEvents:
    async def test_returns_game_events(self, live_context, env_credentials):
        game_id = require_resource(env_credentials, "PLAYHQ_TEST_GAME_ID")

        result = await playhq.execute_action("get_game_events", {"game_id": game_id}, live_context)

        assert "events" in result.result.data
        assert isinstance(result.result.data["events"], dict)
