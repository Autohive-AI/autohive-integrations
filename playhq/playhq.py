"""PlayHQ integration for public sports data and private partner operations."""

from datetime import date
from typing import Any, Dict, Optional
from urllib.parse import quote

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

playhq = Integration.load()

REGION_BASE_URLS = {
    "anz": "https://api.playhq.com",
    "europe": "https://api.euprod.playhq.com",
    "canada": "https://api.caprod.playhq.com",
}

REQUEST_FAILED_MESSAGE = "PlayHQ request failed. Verify credentials, inputs, and resource access."


def credentials_from_context(context: ExecutionContext) -> Dict[str, Any]:
    """Return custom-auth fields in both runtime and direct-test shapes."""
    auth = context.auth or {}
    return auth.get("credentials", auth)


def get_credentials(context: ExecutionContext) -> Dict[str, Any]:
    """Return and validate private Partner API credentials."""
    credentials = credentials_from_context(context)
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    region = credentials.get("region", "anz")

    missing = [name for name, value in {"client_id": client_id, "client_secret": client_secret}.items() if not value]
    if missing:
        raise ValueError(f"Missing required PlayHQ credentials: {', '.join(missing)}")
    if region not in REGION_BASE_URLS:
        raise ValueError(f"Unsupported PlayHQ region: {region}")

    return {"client_id": client_id, "client_secret": client_secret, "region": region}


def get_public_credentials(context: ExecutionContext) -> Dict[str, Any]:
    """Return and validate public API-key credentials."""
    credentials = credentials_from_context(context)
    api_key = credentials.get("api_key")
    tenant = credentials.get("tenant")
    region = credentials.get("region", "anz")

    missing = [name for name, value in {"api_key": api_key, "tenant": tenant}.items() if not value]
    if missing:
        raise ValueError(f"Missing required PlayHQ public API credentials: {', '.join(missing)}")
    if region not in REGION_BASE_URLS:
        raise ValueError(f"Unsupported PlayHQ region: {region}")

    return {"api_key": api_key, "tenant": tenant, "region": region}


class PlayHQClient:
    """Small authenticated client for the PlayHQ Partner API."""

    def __init__(self, context: ExecutionContext):
        credentials = get_credentials(context)
        self.context = context
        self.base_url = REGION_BASE_URLS[credentials["region"]]
        self.client_id = credentials["client_id"]
        self.client_secret = credentials["client_secret"]
        self._access_token: Optional[str] = None

    async def get_access_token(self) -> str:
        """Exchange PlayHQ client credentials for a short-lived JWT."""
        if self._access_token:
            return self._access_token

        response = await self.context.fetch(
            f"{self.base_url}/auth",
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"clientId": self.client_id, "clientSecret": self.client_secret},
        )
        token_data = response.data if isinstance(response.data, dict) else {}
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("PlayHQ authentication response did not include access_token")

        self._access_token = access_token
        return access_token

    async def request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated Partner API request and return the object body."""
        access_token = await self.get_access_token()
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        response = await self.context.fetch(
            f"{self.base_url}{endpoint}",
            method=method,
            headers=headers,
            params=params or None,
            json=json,
        )
        if response.data is None:
            return {}
        if not isinstance(response.data, (dict, list)):
            raise ValueError("PlayHQ response body was not a JSON object or array")
        return response.data


class PlayHQPublicClient:
    """Client for PlayHQ endpoints authenticated by API key and tenant."""

    def __init__(self, context: ExecutionContext):
        credentials = get_public_credentials(context)
        self.context = context
        self.base_url = REGION_BASE_URLS[credentials["region"]]
        self.api_key = credentials["api_key"]
        self.tenant = credentials["tenant"]

    async def request(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a public API GET request and return the parsed object body."""
        response = await self.context.fetch(
            f"{self.base_url}{endpoint}",
            method="GET",
            headers={"Accept": "application/json", "x-api-key": self.api_key, "x-phq-tenant": self.tenant},
            params=params or None,
        )
        if not isinstance(response.data, (dict, list)):
            raise ValueError("PlayHQ response body was not a JSON object or array")
        return response.data


def page_data(payload: Any, key: str) -> Dict[str, Any]:
    """Normalize a PlayHQ paginated response for an action result."""
    if isinstance(payload, list):
        return {key: payload, "metadata": {}}
    data = payload.get("data", payload.get(key, []))
    return {key: data, "metadata": payload.get("metadata", {})}


def object_data(payload: Any, key: str) -> Dict[str, Any]:
    """Normalize a single-object response for an action result."""
    if isinstance(payload, list):
        return {key: payload}
    return {key: payload.get("data", payload.get(key, payload))}


def path_identifier(value: str) -> str:
    """Encode an API identifier before placing it in a URL path."""
    return quote(value, safe="")


@playhq.action("list_organisations")
class ListOrganisationsAction(ActionHandler):
    """List partner-accessible organisations with cursor pagination."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"limit": inputs.get("limit", 10), "type": inputs.get("type", "ALL")}
            if inputs.get("cursor"):
                params["cursor"] = inputs["cursor"]
            payload = await PlayHQClient(context).request("/partner/v2/organisations", params=params)
            data = payload.get("data", {})
            organisations = data.get("organisations", []) if isinstance(data, dict) else []
            return ActionResult(data={"organisations": organisations, "metadata": payload.get("metadata", {})})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_teams_for_organisation")
class ListTeamsForOrganisationAction(ActionHandler):
    """List teams beneath an association organisation."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            organisation_id = path_identifier(inputs["organisation_id"])
            params = {"cursor": inputs["cursor"]} if inputs.get("cursor") else {}
            payload = await PlayHQClient(context).request(
                f"/partner/v1/organisations/{organisation_id}/teams",
                params=params,
            )
            return ActionResult(data=page_data(payload, "teams"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_games_for_organisation")
class ListGamesForOrganisationAction(ActionHandler):
    """List games for an organisation within an inclusive date range."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            start_date = date.fromisoformat(inputs["start_date"])
            end_date = date.fromisoformat(inputs["end_date"])
            if end_date < start_date:
                raise ValueError("end_date must be on or after start_date")

            params = {
                "limit": inputs.get("limit", 10),
                "startDate": inputs["start_date"],
                "endDate": inputs["end_date"],
                "visibility": inputs.get("visibility", "all"),
            }
            if inputs.get("cursor"):
                params["cursor"] = inputs["cursor"]
            payload = await PlayHQClient(context).request(
                f"/partner/v2/organisations/{path_identifier(inputs['organisation_id'])}/games",
                params=params,
            )
            return ActionResult(data=page_data(payload, "games"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_game_summary")
class GetGameSummaryAction(ActionHandler):
    """Get the private v2 summary for a game within the partner scope."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v2/games/{path_identifier(inputs['game_id'])}/summary"
            )
            if not isinstance(payload, dict):
                raise ValueError("PlayHQ summary response was not a JSON object")
            return ActionResult(data={"summary": payload.get("data", {})})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_game_events")
class GetGameEventsAction(ActionHandler):
    """Get electronic-scoring events captured for a game."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/games/{path_identifier(inputs['game_id'])}/events"
            )
            return ActionResult(data={"events": payload.get("data", {})})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


# Public API-key actions


@playhq.action("list_seasons_for_organisation")
class ListSeasonsForOrganisationAction(ActionHandler):
    """List competition seasons for an association organisation."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v1/organisations/{path_identifier(inputs['organisation_id'])}/seasons",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=page_data(payload, "seasons"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_teams_for_season")
class ListTeamsForSeasonAction(ActionHandler):
    """List teams participating in a competition season."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v1/seasons/{path_identifier(inputs['season_id'])}/teams",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=page_data(payload, "teams"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_grades_for_season")
class ListGradesForSeasonAction(ActionHandler):
    """List grades beneath a competition season."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v1/seasons/{path_identifier(inputs['season_id'])}/grades",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=page_data(payload, "grades"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_team_fixture")
class GetTeamFixtureAction(ActionHandler):
    """Get fixture information for a team."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v1/teams/{path_identifier(inputs['team_id'])}/fixture",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=page_data(payload, "games"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_grade_fixture")
class GetGradeFixtureAction(ActionHandler):
    """Get the current v2 fixture for a grade."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v2/grades/{path_identifier(inputs['grade_id'])}/games"
            )
            return ActionResult(data=object_data(payload, "fixture"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_grade_ladder")
class GetGradeLadderAction(ActionHandler):
    """Get the current v2 ladder for a grade."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v2/grades/{path_identifier(inputs['grade_id'])}/ladder"
            )
            return ActionResult(data=object_data(payload, "ladder"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_grade_player_statistics")
class ListGradePlayerStatisticsAction(ActionHandler):
    """List player statistics for a grade."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"limit": inputs.get("limit", 100)}
            if inputs.get("sort"):
                params["sort"] = inputs["sort"]
            if inputs.get("cursor"):
                params["cursor"] = inputs["cursor"]
            payload = await PlayHQPublicClient(context).request(
                f"/v1/grades/{path_identifier(inputs['grade_id'])}/profiles/statistics",
                params=params,
            )
            return ActionResult(data=page_data(payload, "statistics"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_public_game_summary_v1")
class GetPublicGameSummaryV1Action(ActionHandler):
    """Get a public v1 game summary for territory-based sports."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v1/games/{path_identifier(inputs['game_id'])}/summary",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=object_data(payload, "summary"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_public_game_summary_v2")
class GetPublicGameSummaryV2Action(ActionHandler):
    """Get a public v2 game summary."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQPublicClient(context).request(
                f"/v2/games/{path_identifier(inputs['game_id'])}/summary",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=object_data(payload, "summary"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


# Extended private Partner API actions


@playhq.action("get_private_game_summary_v1")
class GetPrivateGameSummaryV1Action(ActionHandler):
    """Get the private v1 summary used by territory-based sports."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/games/{path_identifier(inputs['game_id'])}/summary"
            )
            return ActionResult(data=object_data(payload, "summary"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("set_game_live_streaming")
class SetGameLiveStreamingAction(ActionHandler):
    """Enable or disable live streaming for a game."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/games/{path_identifier(inputs['game_id'])}/live-streaming",
                method="PUT",
                json={"liveStreamingEnabled": inputs["enabled"]},
            )
            return ActionResult(data={"result": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_game_signed_url")
class GetGameSignedUrlAction(ActionHandler):
    """Create a time-limited referee resource URL for a game."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/games/{path_identifier(inputs['game_id'])}/get-signed-url",
                method="POST",
                json={"firstName": inputs["first_name"], "lastName": inputs["last_name"], "userId": inputs["user_id"]},
            )
            return ActionResult(data={"signed_url": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_games_for_organisation_on_date")
class ListGamesForOrganisationOnDateAction(ActionHandler):
    """List games for an organisation on one date using the v1 endpoint."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            date.fromisoformat(inputs["date"])
            payload = await PlayHQClient(context).request(
                f"/partner/v1/organisations/{path_identifier(inputs['organisation_id'])}/games/{inputs['date']}",
                params={"cursor": inputs["cursor"]} if inputs.get("cursor") else {},
            )
            return ActionResult(data=page_data(payload, "games"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_profile_dependants")
class ListProfileDependantsAction(ActionHandler):
    """List tenant-visible dependants for a PlayHQ profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/profiles/{path_identifier(inputs['profile_id'])}/dependants"
            )
            return ActionResult(data=page_data(payload, "dependants"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_profile_career_statistics")
class GetProfileCareerStatisticsAction(ActionHandler):
    """Get career statistics for a profile and optional participant role."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/profiles/{path_identifier(inputs['profile_id'])}/statistics/career",
                params={"role": inputs["role"]} if inputs.get("role") else {},
            )
            return ActionResult(data=object_data(payload, "statistics"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_profile_statistic_seasons")
class ListProfileStatisticSeasonsAction(ActionHandler):
    """List seasons in which a profile earned statistics."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/profiles/{path_identifier(inputs['profile_id'])}/statistics/seasons",
                params={"role": inputs["role"]} if inputs.get("role") else {},
            )
            return ActionResult(data=page_data(payload, "seasons"))
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("get_profile_season_statistics")
class GetProfileSeasonStatisticsAction(ActionHandler):
    """Get a profile's statistics for one season."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/profiles/{path_identifier(inputs['profile_id'])}/statistics/seasons/"
                f"{path_identifier(inputs['season_id'])}",
                params={"role": inputs["role"]} if inputs.get("role") else {},
            )
            statistics = payload.get("data", payload) if isinstance(payload, dict) else payload
            return ActionResult(data={"statistics": statistics})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("list_webhook_filter_entity_ids")
class ListWebhookFilterEntityIdsAction(ActionHandler):
    """List entity IDs configured on a webhook subscription filter."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            endpoint = webhook_filter_endpoint(inputs["subscriber_id"], inputs["subscription_id"], inputs["entity"])
            payload = await PlayHQClient(context).request(endpoint)
            entity_ids = payload if isinstance(payload, list) else payload.get("data", payload.get("ids", []))
            return ActionResult(data={"entity_ids": entity_ids})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("add_webhook_filter_entity_id")
class AddWebhookFilterEntityIdAction(ActionHandler):
    """Add an entity ID to a webhook subscription filter."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            endpoint = (
                f"{webhook_filter_endpoint(inputs['subscriber_id'], inputs['subscription_id'], inputs['entity'])}/"
                f"{path_identifier(inputs['entity_id'])}"
            )
            payload = await PlayHQClient(context).request(endpoint, method="PUT")
            return ActionResult(data={"result": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("remove_webhook_filter_entity_id")
class RemoveWebhookFilterEntityIdAction(ActionHandler):
    """Remove an entity ID from a webhook subscription filter."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            endpoint = (
                f"{webhook_filter_endpoint(inputs['subscriber_id'], inputs['subscription_id'], inputs['entity'])}/"
                f"{path_identifier(inputs['entity_id'])}"
            )
            payload = await PlayHQClient(context).request(endpoint, method="DELETE")
            return ActionResult(data={"result": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("set_game_payment_contract")
class SetGamePaymentContractAction(ActionHandler):
    """Activate or deactivate an organisation's game payment contract."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                f"/partner/v1/organisations/{path_identifier(inputs['organisation_id'])}/game-payment-contracts",
                method="PUT",
                json={"status": inputs["status"]},
            )
            return ActionResult(data={"result": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


@playhq.action("link_referee_profile")
class LinkRefereeProfileAction(ActionHandler):
    """Link an external referee user ID to a PlayHQ profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            payload = await PlayHQClient(context).request(
                "/partner/v1/referees/link",
                method="POST",
                json={
                    "provider": inputs["provider"],
                    "externalUserId": inputs["external_user_id"],
                    "profileId": inputs["profile_id"],
                },
            )
            return ActionResult(data={"result": payload.get("data", payload)})
        except Exception:
            return ActionError(message=REQUEST_FAILED_MESSAGE)


def webhook_filter_endpoint(subscriber_id: str, subscription_id: str, entity: str) -> str:
    """Build the common webhook-filter endpoint with encoded identifiers."""
    return (
        f"/partner/v1/webhooks/subscribers/{path_identifier(subscriber_id)}/subscriptions/"
        f"{path_identifier(subscription_id)}/filters/{path_identifier(entity)}/ids"
    )
