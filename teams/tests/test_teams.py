import asyncio
import os
import sys

from context import teams  # noqa
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

ACCESS_TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEAMS_TOKEN", "")
TEST_AUTH = {"credentials": {"access_token": ACCESS_TOKEN}}


async def test_list_teams():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await teams.execute_action("list_teams", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        assert "teams" in data
        print(f"[OK] list_teams: {len(data['teams'])} teams")


async def test_list_chats():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await teams.execute_action("list_chats", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        assert "chats" in data
        print(f"[OK] list_chats: {len(data['chats'])} chats")


async def test_list_channels():
    teams_result_ctx = ExecutionContext(auth=TEST_AUTH)
    async with teams_result_ctx as context:
        teams_resp = await teams.execute_action("list_teams", {}, context)
        teams_list = teams_resp.result.data.get("teams", [])
        if not teams_list:
            print("[SKIP] list_channels: no teams available")
            return
        team_id = teams_list[0]["id"]
        result = await teams.execute_action("list_channels", {"team_id": team_id}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_channels: {len(data['channels'])} channels in team {team_id}")


async def test_list_messages():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        teams_resp = await teams.execute_action("list_teams", {}, context)
        teams_list = teams_resp.result.data.get("teams", [])
        if not teams_list:
            print("[SKIP] list_messages: no teams available")
            return
        team_id = teams_list[0]["id"]
        channels_resp = await teams.execute_action("list_channels", {"team_id": team_id}, context)
        channels = channels_resp.result.data.get("channels", [])
        if not channels:
            print("[SKIP] list_messages: no channels available")
            return
        channel_id = channels[0]["id"]
        result = await teams.execute_action(
            "list_messages", {"team_id": team_id, "channel_id": channel_id, "limit": 5}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_messages: {len(data['messages'])} messages")


if __name__ == "__main__":
    asyncio.run(test_list_teams())
    asyncio.run(test_list_chats())
    asyncio.run(test_list_channels())
    asyncio.run(test_list_messages())
