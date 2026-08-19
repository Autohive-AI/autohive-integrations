import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

SAMPLE_FORK = {
    "id": 42,
    "name": "Hello-World",
    "full_name": "monalisa/Hello-World",
    "owner": {"login": "monalisa", "avatar_url": "https://avatars.githubusercontent.com/u/2"},
    "private": False,
    "fork": True,
    "default_branch": "main",
    "created_at": "2024-01-01T00:00:00Z",
    "clone_url": "https://github.com/monalisa/Hello-World.git",
    "ssh_url": "git@github.com:monalisa/Hello-World.git",
    "html_url": "https://github.com/monalisa/Hello-World",
    "parent": {"full_name": "octocat/Hello-World"},
}

SAMPLE_TREE = {
    "sha": "tree-sha-1",
    "url": "https://api.github.com/repos/octocat/Hello-World/git/trees/tree-sha-1",
    "truncated": False,
    "tree": [
        {
            "path": "README.md",
            "mode": "100644",
            "type": "blob",
            "sha": "blob-sha-1",
            "size": 30,
            "url": "https://api.github.com/repos/octocat/Hello-World/git/blobs/blob-sha-1",
        },
        {
            "path": "src",
            "mode": "040000",
            "type": "tree",
            "sha": "tree-sha-2",
            "url": "https://api.github.com/repos/octocat/Hello-World/git/trees/tree-sha-2",
        },
    ],
}

SAMPLE_COLLABORATOR = {
    "login": "octocat",
    "id": 1,
    "node_id": "MDQ6VXNlcjE=",
    "avatar_url": "https://avatars.githubusercontent.com/u/1",
    "url": "https://api.github.com/users/octocat",
    "html_url": "https://github.com/octocat",
    "role_name": "write",
    "permissions": {"pull": True, "triage": True, "push": True, "maintain": False, "admin": False},
}

# ---- push_files: the five Git Data API responses, in call order ----

SAMPLE_HEAD_REF = {
    "ref": "refs/heads/main",
    "node_id": "REF_kwDO",
    "url": "https://api.github.com/repos/octocat/Hello-World/git/refs/heads/main",
    "object": {"type": "commit", "sha": "head-commit-sha", "url": "https://api.github.com/x"},
}

SAMPLE_BASE_COMMIT = {
    "sha": "head-commit-sha",
    "message": "Earlier commit",
    "tree": {"sha": "base-tree-sha", "url": "https://api.github.com/y"},
    "parents": [],
}

SAMPLE_NEW_TREE = {"sha": "new-tree-sha", "url": "https://api.github.com/z", "truncated": False, "tree": []}

SAMPLE_NEW_COMMIT = {
    "sha": "new-commit-sha",
    "message": "Add two files",
    "html_url": "https://github.com/octocat/Hello-World/commit/new-commit-sha",
    "tree": {"sha": "new-tree-sha"},
    "parents": [{"sha": "head-commit-sha"}],
    "author": {"name": "Octocat", "email": "octocat@github.com", "date": "2024-01-01T00:00:00Z"},
}

SAMPLE_UPDATED_REF = {
    "ref": "refs/heads/main",
    "url": "https://api.github.com/repos/octocat/Hello-World/git/refs/heads/main",
    "object": {"type": "commit", "sha": "new-commit-sha", "url": "https://api.github.com/x"},
}

SAMPLE_BLOB = {"sha": "blob-sha-binary", "url": "https://api.github.com/blob"}

PUSH_INPUTS = {
    "owner": "octocat",
    "repo": "Hello-World",
    "branch": "main",
    "message": "Add two files",
    "files": [
        {"path": "docs/one.md", "content": "one"},
        {"path": "docs/two.md", "content": "two"},
    ],
}


def _ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def _push_sequence():
    """The happy-path responses for the five sequential Git Data calls."""
    return [
        _ok(SAMPLE_HEAD_REF),
        _ok(SAMPLE_BASE_COMMIT),
        _ok(SAMPLE_NEW_TREE, status=201),
        _ok(SAMPLE_NEW_COMMIT, status=201),
        _ok(SAMPLE_UPDATED_REF),
    ]


# ---- Fork ----


class TestForkRepository:
    @pytest.mark.asyncio
    async def test_returns_fork_data(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_FORK, status=202)

        result = await github.execute_action(
            "fork_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data["full_name"] == "monalisa/Hello-World"
        assert result.result.data["owner"]["login"] == "monalisa"
        assert result.result.data["url"] == "https://github.com/monalisa/Hello-World"
        assert result.result.data["source"] == "octocat/Hello-World"
        # Forking is asynchronous — the caller must know the fork is not ready yet.
        assert result.result.data["pending"] is True

    @pytest.mark.asyncio
    async def test_request_uses_post_to_forks_endpoint(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_FORK, status=202)

        await github.execute_action("fork_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/repos/octocat/Hello-World/forks")
        assert mock_context.fetch.call_args.kwargs["json"] == {}

    @pytest.mark.asyncio
    async def test_optional_body_params_are_sent(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_FORK, status=202)

        await github.execute_action(
            "fork_repository",
            {
                "owner": "octocat",
                "repo": "Hello-World",
                "organization": "acme",
                "name": "hello-fork",
                "default_branch_only": True,
            },
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {
            "organization": "acme",
            "name": "hello-fork",
            "default_branch_only": True,
        }

    @pytest.mark.asyncio
    async def test_missing_parent_falls_back_to_requested_source(self, mock_context):
        payload = {key: value for key, value in SAMPLE_FORK.items() if key != "parent"}
        mock_context.fetch.return_value = _ok(payload, status=202)

        result = await github.execute_action(
            "fork_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data["source"] == "octocat/Hello-World"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action(
            "fork_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


# ---- Tree ----


class TestGetRepositoryTree:
    @pytest.mark.asyncio
    async def test_returns_tree_entries(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TREE)

        result = await github.execute_action(
            "get_repository_tree", {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main"}, mock_context
        )

        assert result.result.data["sha"] == "tree-sha-1"
        assert result.result.data["entry_count"] == 2
        assert result.result.data["tree"][0]["path"] == "README.md"
        assert result.result.data["tree"][1]["size"] is None

    @pytest.mark.asyncio
    async def test_truncated_flag_is_surfaced(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_TREE, "truncated": True})

        result = await github.execute_action(
            "get_repository_tree", {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main"}, mock_context
        )

        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_truncated_defaults_to_false_when_absent(self, mock_context):
        payload = {key: value for key, value in SAMPLE_TREE.items() if key != "truncated"}
        mock_context.fetch.return_value = _ok(payload)

        result = await github.execute_action(
            "get_repository_tree", {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main"}, mock_context
        )

        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_recursive_sends_recursive_param(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TREE)

        await github.execute_action(
            "get_repository_tree",
            {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main", "recursive": True},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["params"] == {"recursive": "1"}

    @pytest.mark.asyncio
    async def test_non_recursive_omits_recursive_param(self, mock_context):
        # GitHub treats *any* value of `recursive` as true, so it must be absent.
        mock_context.fetch.return_value = _ok(SAMPLE_TREE)

        await github.execute_action(
            "get_repository_tree",
            {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main", "recursive": False},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_ref_with_slash_keeps_path_segments(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TREE)

        await github.execute_action(
            "get_repository_tree",
            {"owner": "octocat", "repo": "Hello-World", "tree_sha": "feature/new thing"},
            mock_context,
        )

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/git/trees/feature/new%20thing")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await github.execute_action(
            "get_repository_tree", {"owner": "octocat", "repo": "Hello-World", "tree_sha": "main"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Not Found" in result.result.message


# ---- Collaborators ----


class TestListRepositoryCollaborators:
    @pytest.mark.asyncio
    async def test_returns_shaped_collaborators(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_COLLABORATOR])

        result = await github.execute_action(
            "list_repository_collaborators", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        collaborator = result.result.data[0]
        assert collaborator["login"] == "octocat"
        assert collaborator["url"] == "https://github.com/octocat"
        assert collaborator["role_name"] == "write"
        assert collaborator["permissions"]["push"] is True
        assert collaborator["permissions"]["admin"] is False

    @pytest.mark.asyncio
    async def test_filters_are_sent_as_params(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_COLLABORATOR])

        await github.execute_action(
            "list_repository_collaborators",
            {"owner": "octocat", "repo": "Hello-World", "affiliation": "direct", "permission": "push"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["affiliation"] == "direct"
        assert params["permission"] == "push"
        assert "collaborators" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_missing_permissions_object_is_tolerated(self, mock_context):
        payload = {key: value for key, value in SAMPLE_COLLABORATOR.items() if key != "permissions"}
        mock_context.fetch.return_value = _ok([payload])

        result = await github.execute_action(
            "list_repository_collaborators", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data[0]["permissions"]["push"] is None

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        first_page = [{**SAMPLE_COLLABORATOR, "id": index, "login": f"user{index}"} for index in range(100)]
        mock_context.fetch.side_effect = [_ok(first_page), _ok([{**SAMPLE_COLLABORATOR, "id": 100, "login": "last"}])]

        result = await github.execute_action(
            "list_repository_collaborators", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101
        assert result.result.data[-1]["login"] == "last"

    @pytest.mark.asyncio
    async def test_limit_truncates_results(self, mock_context):
        mock_context.fetch.return_value = _ok(
            [{**SAMPLE_COLLABORATOR, "id": index, "login": f"user{index}"} for index in range(2)]
        )

        result = await github.execute_action(
            "list_repository_collaborators", {"owner": "octocat", "repo": "Hello-World", "limit": 2}, mock_context
        )

        assert len(result.result.data) == 2
        assert mock_context.fetch.call_args.kwargs["params"]["per_page"] == 2

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await github.execute_action(
            "list_repository_collaborators", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- Push files (Git Data API composite) ----


class TestPushFiles:
    @pytest.mark.asyncio
    async def test_returns_commit_summary(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        data = result.result.data
        assert data["commit"]["sha"] == "new-commit-sha"
        assert data["commit"]["url"] == "https://github.com/octocat/Hello-World/commit/new-commit-sha"
        assert data["commit"]["author"]["name"] == "Octocat"
        assert data["branch"] == "main"
        assert data["tree_sha"] == "new-tree-sha"
        assert data["parent_sha"] == "head-commit-sha"
        assert data["written_paths"] == ["docs/one.md", "docs/two.md"]
        assert data["deleted_paths"] == []
        assert data["files_changed"] == 2

    @pytest.mark.asyncio
    async def test_calls_the_five_endpoints_in_order(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        calls = mock_context.fetch.call_args_list
        assert len(calls) == 5

        assert calls[0].args[0].endswith("/repos/octocat/Hello-World/git/ref/heads/main")
        assert calls[0].kwargs.get("method", "GET") == "GET"

        assert calls[1].args[0].endswith("/repos/octocat/Hello-World/git/commits/head-commit-sha")
        assert calls[1].kwargs.get("method", "GET") == "GET"

        assert calls[2].args[0].endswith("/repos/octocat/Hello-World/git/trees")
        assert calls[2].kwargs["method"] == "POST"

        assert calls[3].args[0].endswith("/repos/octocat/Hello-World/git/commits")
        assert calls[3].kwargs["method"] == "POST"

        assert calls[4].args[0].endswith("/repos/octocat/Hello-World/git/refs/heads/main")
        assert calls[4].kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_tree_payload_layers_on_base_tree_with_inline_content(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        tree_payload = mock_context.fetch.call_args_list[2].kwargs["json"]
        assert tree_payload["base_tree"] == "base-tree-sha"
        assert tree_payload["tree"] == [
            {"path": "docs/one.md", "mode": "100644", "type": "blob", "content": "one"},
            {"path": "docs/two.md", "mode": "100644", "type": "blob", "content": "two"},
        ]

    @pytest.mark.asyncio
    async def test_commit_and_ref_payloads(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        commit_payload = mock_context.fetch.call_args_list[3].kwargs["json"]
        assert commit_payload == {
            "message": "Add two files",
            "tree": "new-tree-sha",
            "parents": ["head-commit-sha"],
        }

        ref_payload = mock_context.fetch.call_args_list[4].kwargs["json"]
        assert ref_payload == {"sha": "new-commit-sha", "force": False}

    @pytest.mark.asyncio
    async def test_force_is_passed_to_the_ref_update(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action("push_files", {**PUSH_INPUTS, "force": True}, mock_context)

        assert mock_context.fetch.call_args_list[4].kwargs["json"]["force"] is True

    @pytest.mark.asyncio
    async def test_custom_mode_is_used_for_the_tree_entry(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "run.sh", "content": "#!/bin/sh\n", "mode": "100755"}]},
            mock_context,
        )

        entries = mock_context.fetch.call_args_list[2].kwargs["json"]["tree"]
        assert entries == [{"path": "run.sh", "mode": "100755", "type": "blob", "content": "#!/bin/sh\n"}]

    @pytest.mark.asyncio
    async def test_delete_paths_become_null_sha_entries(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        result = await github.execute_action(
            "push_files", {**PUSH_INPUTS, "delete_paths": ["old/gone.txt"]}, mock_context
        )

        entries = mock_context.fetch.call_args_list[2].kwargs["json"]["tree"]
        assert entries[-1] == {"path": "old/gone.txt", "mode": "100644", "type": "blob", "sha": None}
        assert result.result.data["deleted_paths"] == ["old/gone.txt"]
        assert result.result.data["files_changed"] == 3

    @pytest.mark.asyncio
    async def test_base64_file_is_uploaded_as_a_blob(self, mock_context):
        responses = _push_sequence()
        # The blob upload happens between reading the base commit and creating the tree.
        responses.insert(2, _ok(SAMPLE_BLOB, status=201))
        mock_context.fetch.side_effect = responses

        await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "logo.png", "content": "aGVsbG8=", "encoding": "base64"}]},
            mock_context,
        )

        calls = mock_context.fetch.call_args_list
        assert len(calls) == 6
        assert calls[2].args[0].endswith("/repos/octocat/Hello-World/git/blobs")
        assert calls[2].kwargs["json"] == {"content": "aGVsbG8=", "encoding": "base64"}

        entries = calls[3].kwargs["json"]["tree"]
        assert entries == [{"path": "logo.png", "mode": "100644", "type": "blob", "sha": "blob-sha-binary"}]

    @pytest.mark.asyncio
    async def test_empty_files_errors_without_any_request(self, mock_context):
        result = await github.execute_action("push_files", {**PUSH_INPUTS, "files": []}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Nothing to commit" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_path_errors_without_any_request(self, mock_context):
        result = await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "a.txt", "content": "1"}, {"path": "a.txt", "content": "2"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "more than once" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_path_also_listed_for_deletion_errors(self, mock_context):
        result = await github.execute_action(
            "push_files", {**PUSH_INPUTS, "delete_paths": ["docs/one.md"]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "more than once" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_content_is_rejected_before_any_request(self, mock_context):
        # The input schema marks path and content as required for every file, so
        # the platform rejects this before the handler runs; the handler keeps
        # its own guard as a backstop.
        result = await github.execute_action("push_files", {**PUSH_INPUTS, "files": [{"path": "a.txt"}]}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "content" in result.result["message"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_encoding_is_rejected_before_any_request(self, mock_context):
        result = await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "a.txt", "content": "x", "encoding": "hex"}]},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        assert "encoding" in result.result["message"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_base64_errors_without_any_request(self, mock_context):
        result = await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "logo.png", "content": "not!!base64", "encoding": "base64"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not valid base64" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_utf8_text_is_rejected_rather_than_corrupted(self, mock_context):
        result = await github.execute_action(
            "push_files",
            {**PUSH_INPUTS, "files": [{"path": "a.txt", "content": "\ud800"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not valid UTF-8" in result.result.message
        assert "base64" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_absolute_path_is_rejected(self, mock_context):
        result = await github.execute_action(
            "push_files", {**PUSH_INPUTS, "files": [{"path": "/a.txt", "content": "x"}]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "relative to the repository root" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_step_one_failure_names_the_step(self, mock_context):
        mock_context.fetch.side_effect = Exception("404 Not Found")

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "step 1 of 5" in result.result.message
        assert "Nothing was committed" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_tree_creation_failure_stops_before_committing(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_HEAD_REF),
            _ok(SAMPLE_BASE_COMMIT),
            Exception("422 Unprocessable Entity"),
        ]

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "step 3 of 5" in result.result.message
        assert "No commit was created" in result.result.message
        # No commit call and no ref update were attempted.
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_ref_update_failure_reports_the_orphaned_commit(self, mock_context):
        responses = _push_sequence()
        responses[-1] = Exception("422 Update is not a fast forward")
        mock_context.fetch.side_effect = responses

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "step 5 of 5" in result.result.message
        assert "new-commit-sha" in result.result.message
        assert "head-commit-sha" in result.result.message
        assert "force" in result.result.message

    @pytest.mark.asyncio
    async def test_branch_without_head_commit_errors(self, mock_context):
        mock_context.fetch.side_effect = [_ok({"ref": "refs/heads/main", "object": {}})]

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "step 1 of 5" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_branch_with_slash_keeps_path_segments(self, mock_context):
        mock_context.fetch.side_effect = _push_sequence()

        await github.execute_action("push_files", {**PUSH_INPUTS, "branch": "feature/new"}, mock_context)

        calls = mock_context.fetch.call_args_list
        assert calls[0].args[0].endswith("/git/ref/heads/feature/new")
        assert calls[4].args[0].endswith("/git/refs/heads/feature/new")

    @pytest.mark.asyncio
    async def test_missing_token_returns_action_error(self, mock_context):
        mock_context.auth = {"credentials": {}}

        result = await github.execute_action("push_files", PUSH_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "token" in result.result.message.lower()
