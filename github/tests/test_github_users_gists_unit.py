"""Unit tests for the GitHub team and gist actions."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit


SAMPLE_ORG_TEAM = {
    "id": 1,
    "node_id": "MDQ6VGVhbTE=",
    "name": "Justice League",
    "slug": "justice-league",
    "description": "A great team",
    "privacy": "closed",
    "notification_setting": "notifications_enabled",
    "permission": "push",
    "url": "https://api.github.com/teams/1",
    "html_url": "https://github.com/orgs/github/teams/justice-league",
    "parent": None,
}

SAMPLE_CHILD_TEAM = {
    **SAMPLE_ORG_TEAM,
    "id": 2,
    "name": "Sidekicks",
    "slug": "sidekicks",
    "parent": {"id": 1, "name": "Justice League", "slug": "justice-league"},
}

SAMPLE_USER_TEAM = {
    **SAMPLE_ORG_TEAM,
    "members_count": 3,
    "repos_count": 10,
    "created_at": "2017-07-14T16:53:42Z",
    "updated_at": "2017-08-17T12:37:15Z",
    "organization": {"login": "github", "id": 9919},
}

SAMPLE_MEMBER = {
    "login": "octocat",
    "id": 1,
    "type": "User",
    "site_admin": False,
    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
    "html_url": "https://github.com/octocat",
}

SAMPLE_GIST_FILE = {
    "filename": "hello_world.rb",
    "type": "application/x-ruby",
    "language": "Ruby",
    "raw_url": "https://gist.githubusercontent.com/octocat/raw/hello_world.rb",
    "size": 175,
    "truncated": False,
    "content": "class HelloWorld\n  def initialize(name)\n  end\nend",
    "encoding": "utf-8",
}

SAMPLE_GIST = {
    "id": "6cad326836d38bd3a7ae",
    "description": "Hello World Examples",
    "public": True,
    "owner": {
        "login": "octocat",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "html_url": "https://github.com/octocat",
    },
    "files": {"hello_world.rb": SAMPLE_GIST_FILE},
    "truncated": False,
    "comments": 0,
    "created_at": "2010-04-14T02:15:15Z",
    "updated_at": "2011-06-20T11:34:15Z",
    "git_pull_url": "https://gist.github.com/6cad326836d38bd3a7ae.git",
    "html_url": "https://gist.github.com/6cad326836d38bd3a7ae",
}

# What a list response actually looks like: no content, no per-file truncated flag.
SAMPLE_GIST_LIST_ENTRY = {
    **SAMPLE_GIST,
    "files": {
        "hello_world.rb": {
            "filename": "hello_world.rb",
            "type": "application/x-ruby",
            "language": "Ruby",
            "raw_url": "https://gist.githubusercontent.com/octocat/raw/hello_world.rb",
            "size": 175,
        }
    },
}


def _ok(data):
    return FetchResponse(status=200, headers={}, data=data)


class TestGetTeams:
    @pytest.mark.asyncio
    async def test_returns_org_teams(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_ORG_TEAM])

        result = await github.execute_action("get_teams", {"org": "github"}, mock_context)

        assert result.result.data == [
            {
                "id": 1,
                "name": "Justice League",
                "slug": "justice-league",
                "description": "A great team",
                "privacy": "closed",
                "notification_setting": "notifications_enabled",
                "permission": "push",
                "parent": None,
                "organization": None,
                "members_count": None,
                "repos_count": None,
                "url": "https://github.com/orgs/github/teams/justice-league",
            }
        ]

    @pytest.mark.asyncio
    async def test_uses_org_endpoint_when_org_given(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_ORG_TEAM])

        await github.execute_action("get_teams", {"org": "github"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/orgs/github/teams"

    @pytest.mark.asyncio
    async def test_falls_back_to_user_teams_without_org(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_USER_TEAM])

        result = await github.execute_action("get_teams", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/user/teams"
        assert result.result.data[0]["organization"] == "github"
        assert result.result.data[0]["members_count"] == 3
        assert result.result.data[0]["repos_count"] == 10

    @pytest.mark.asyncio
    async def test_flattens_parent_team(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_CHILD_TEAM])

        result = await github.execute_action("get_teams", {"org": "github"}, mock_context)

        assert result.result.data[0]["parent"] == {"id": 1, "name": "Justice League", "slug": "justice-league"}

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok([dict(SAMPLE_ORG_TEAM, id=index) for index in range(100)]),
            _ok([dict(SAMPLE_ORG_TEAM, id=100)]),
        ]

        result = await github.execute_action("get_teams", {"org": "github"}, mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, mock_context):
        mock_context.fetch.return_value = _ok([dict(SAMPLE_ORG_TEAM, id=index) for index in range(5)])

        result = await github.execute_action("get_teams", {"org": "github", "limit": 2}, mock_context)

        assert len(result.result.data) == 2

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await github.execute_action("get_teams", {"org": "github"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not Found" in result.result.message


class TestGetTeamMembers:
    @pytest.mark.asyncio
    async def test_returns_members(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_MEMBER])

        result = await github.execute_action(
            "get_team_members", {"org": "github", "team_slug": "justice-league"}, mock_context
        )

        assert result.result.data == [
            {
                "login": "octocat",
                "id": 1,
                "type": "User",
                "site_admin": False,
                "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                "url": "https://github.com/octocat",
            }
        ]

    @pytest.mark.asyncio
    async def test_addresses_team_by_slug(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_MEMBER])

        await github.execute_action("get_team_members", {"org": "github", "team_slug": "justice-league"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == (
            "https://api.github.com/orgs/github/teams/justice-league/members"
        )

    @pytest.mark.asyncio
    async def test_defaults_role_to_all(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_MEMBER])

        await github.execute_action("get_team_members", {"org": "github", "team_slug": "justice-league"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["role"] == "all"

    @pytest.mark.asyncio
    async def test_passes_role_filter(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_MEMBER])

        await github.execute_action(
            "get_team_members",
            {"org": "github", "team_slug": "justice-league", "role": "maintainer"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["params"]["role"] == "maintainer"

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok([dict(SAMPLE_MEMBER, id=index) for index in range(100)]),
            _ok([dict(SAMPLE_MEMBER, id=100)]),
        ]

        result = await github.execute_action(
            "get_team_members", {"org": "github", "team_slug": "justice-league"}, mock_context
        )

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101


class TestGetGist:
    @pytest.mark.asyncio
    async def test_returns_file_content(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action("get_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        gist_file = result.result.data["files"]["hello_world.rb"]
        assert gist_file["content"].startswith("class HelloWorld")
        assert gist_file["encoding"] == "utf-8"
        assert gist_file["truncated"] is False
        assert result.result.data["url"] == "https://gist.github.com/6cad326836d38bd3a7ae"
        assert result.result.data["owner"]["login"] == "octocat"

    @pytest.mark.asyncio
    async def test_surfaces_file_level_truncation(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                **SAMPLE_GIST,
                "files": {"big.txt": {**SAMPLE_GIST_FILE, "filename": "big.txt", "truncated": True, "size": 2000000}},
            }
        )

        result = await github.execute_action("get_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        assert result.result.data["files"]["big.txt"]["truncated"] is True
        assert result.result.data["files"]["big.txt"]["raw_url"]
        assert result.result.data["git_pull_url"]

    @pytest.mark.asyncio
    async def test_surfaces_gist_level_truncation(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_GIST, "truncated": True})

        result = await github.execute_action("get_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_tolerates_missing_owner(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_GIST, "owner": None})

        result = await github.execute_action("get_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        assert result.result.data["owner"] is None

    @pytest.mark.asyncio
    async def test_requests_gist_by_id(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action("get_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/gists/6cad326836d38bd3a7ae"


class TestListGists:
    @pytest.mark.asyncio
    async def test_returns_file_metadata_without_content(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_GIST_LIST_ENTRY])

        result = await github.execute_action("list_gists", {}, mock_context)

        gist_file = result.result.data[0]["files"]["hello_world.rb"]
        assert "content" not in gist_file
        assert gist_file["size"] == 175
        assert gist_file["raw_url"]
        assert result.result.data[0]["id"] == "6cad326836d38bd3a7ae"

    @pytest.mark.asyncio
    async def test_uses_authenticated_endpoint_without_username(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_GIST_LIST_ENTRY])

        await github.execute_action("list_gists", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/gists"

    @pytest.mark.asyncio
    async def test_uses_user_endpoint_with_username(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_GIST_LIST_ENTRY])

        await github.execute_action("list_gists", {"username": "octocat"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/users/octocat/gists"

    @pytest.mark.asyncio
    async def test_since_is_sent_as_query_param(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_GIST_LIST_ENTRY])

        await github.execute_action("list_gists", {"since": "2024-01-31"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["since"] == "2024-01-31T00:00:00Z"

    @pytest.mark.asyncio
    async def test_unparseable_since_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_GIST_LIST_ENTRY])

        result = await github.execute_action("list_gists", {"since": "last tuesday"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "ISO 8601" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok([dict(SAMPLE_GIST_LIST_ENTRY, id=str(index)) for index in range(100)]),
            _ok([dict(SAMPLE_GIST_LIST_ENTRY, id="100")]),
        ]

        result = await github.execute_action("list_gists", {}, mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, mock_context):
        mock_context.fetch.return_value = _ok([dict(SAMPLE_GIST_LIST_ENTRY, id=str(index)) for index in range(5)])

        result = await github.execute_action("list_gists", {"limit": 2}, mock_context)

        assert len(result.result.data) == 2


class TestUpdateGist:
    @pytest.mark.asyncio
    async def test_uses_patch(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "description": "Updated"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"
        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/gists/6cad326836d38bd3a7ae"

    @pytest.mark.asyncio
    async def test_description_only_update_sends_no_files(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "description": "Updated"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"description": "Updated"}

    @pytest.mark.asyncio
    async def test_updates_file_content(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist",
            {"gist_id": "6cad326836d38bd3a7ae", "files": {"hello_world.rb": {"content": "puts 'hi'"}}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"files": {"hello_world.rb": {"content": "puts 'hi'"}}}

    @pytest.mark.asyncio
    async def test_renames_file(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist",
            {"gist_id": "6cad326836d38bd3a7ae", "files": {"old.py": {"filename": "new.py"}}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"files": {"old.py": {"filename": "new.py"}}}

    @pytest.mark.asyncio
    async def test_rename_with_content_sends_both_keys(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist",
            {"gist_id": "6cad326836d38bd3a7ae", "files": {"old.py": {"filename": "new.py", "content": "x = 1"}}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["files"]["old.py"] == {
            "content": "x = 1",
            "filename": "new.py",
        }

    @pytest.mark.asyncio
    async def test_delete_files_sends_null(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist",
            {"gist_id": "6cad326836d38bd3a7ae", "delete_files": ["stale.txt"]},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"files": {"stale.txt": None}}

    @pytest.mark.asyncio
    async def test_edit_and_delete_combine(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        await github.execute_action(
            "update_gist",
            {
                "gist_id": "6cad326836d38bd3a7ae",
                "files": {"keep.txt": {"content": "kept"}},
                "delete_files": ["drop.txt"],
            },
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["files"] == {
            "keep.txt": {"content": "kept"},
            "drop.txt": None,
        }

    @pytest.mark.asyncio
    async def test_empty_file_entry_is_rejected_not_sent(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "files": {"hello_world.rb": {}}}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "delete_files" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_null_file_value_is_rejected_not_sent(self, mock_context):
        """A null file value is GitHub's delete idiom; the input schema blocks it before it can reach GitHub."""
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "files": {"hello_world.rb": None}}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_file_edited_and_deleted_is_rejected(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action(
            "update_gist",
            {
                "gist_id": "6cad326836d38bd3a7ae",
                "files": {"both.txt": {"content": "x"}},
                "delete_files": ["both.txt"],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "both.txt" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_update_is_rejected(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action("update_gist", {"gist_id": "6cad326836d38bd3a7ae"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Nothing to update" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_file_metadata_not_content(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_GIST)

        result = await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "description": "Updated"}, mock_context
        )

        assert "content" not in result.result.data["files"]["hello_world.rb"]
        assert result.result.data["files"]["hello_world.rb"]["size"] == 175

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action(
            "update_gist", {"gist_id": "6cad326836d38bd3a7ae", "description": "Updated"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message
