"""
Unit tests for the extended pull request actions.

Covers the PR-editing, diff/files/status, review-comment and pending-review
actions added on top of the original eight PR actions (which are covered by
test_github_prs_unit.py).
"""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

REPO_ARGS = {"owner": "octocat", "repo": "Hello-World", "pull_number": 7}

SAMPLE_USER = {"login": "octocat", "id": 1, "avatar_url": "https://github.com/octocat.png"}

SAMPLE_REPO_REF = {"name": "Hello-World", "full_name": "octocat/Hello-World", "id": 1}

SAMPLE_PR = {
    "id": 100,
    "node_id": "PR_001",
    "number": 7,
    "title": "Fix the bug",
    "body": "This PR fixes the bug",
    "state": "open",
    "draft": False,
    "merged": False,
    "mergeable": True,
    "mergeable_state": "clean",
    "maintainer_can_modify": True,
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-02T00:00:00Z",
    "closed_at": None,
    "merged_at": None,
    "html_url": "https://github.com/octocat/Hello-World/pull/7",
    "user": SAMPLE_USER,
    "head": {"ref": "feature-branch", "sha": "abc123", "label": "octocat:feature-branch", "repo": SAMPLE_REPO_REF},
    "base": {"ref": "main", "sha": "def456", "label": "octocat:main", "repo": SAMPLE_REPO_REF},
}

SAMPLE_FILE = {
    "sha": "bbcd538c",
    "filename": "src/main.py",
    "status": "modified",
    "additions": 10,
    "deletions": 2,
    "changes": 12,
    "blob_url": "https://github.com/octocat/Hello-World/blob/abc123/src/main.py",
    "raw_url": "https://github.com/octocat/Hello-World/raw/abc123/src/main.py",
    "patch": "@@ -1,3 +1,5 @@\n+import os\n",
}

SAMPLE_COMBINED_STATUS = {
    "state": "success",
    "sha": "abc123",
    "total_count": 2,
    "commit_url": "https://api.github.com/repos/octocat/Hello-World/commits/abc123",
    "statuses": [
        {
            "context": "ci/tests",
            "state": "success",
            "description": "All checks passed",
            "target_url": "https://ci.example.com/build/1",
            "created_at": "2021-01-02T00:00:00Z",
            "updated_at": "2021-01-02T00:05:00Z",
        },
        {
            "context": "ci/lint",
            "state": "success",
            "description": None,
            "target_url": None,
            "created_at": "2021-01-02T00:00:00Z",
            "updated_at": "2021-01-02T00:04:00Z",
        },
    ],
}

SAMPLE_REVIEW_COMMENT = {
    "id": 900,
    "body": "Consider renaming this",
    "path": "src/main.py",
    "line": 12,
    "start_line": None,
    "side": "RIGHT",
    "start_side": None,
    "diff_hunk": "@@ -1,3 +1,5 @@",
    "commit_id": "abc123",
    "in_reply_to_id": None,
    "pull_request_review_id": 55,
    "author_association": "COLLABORATOR",
    "created_at": "2021-01-03T00:00:00Z",
    "updated_at": "2021-01-03T00:00:00Z",
    "user": SAMPLE_USER,
    "html_url": "https://github.com/octocat/Hello-World/pull/7#discussion_r900",
}

SAMPLE_COMMIT = {
    "sha": "abc123",
    "html_url": "https://github.com/octocat/Hello-World/commit/abc123",
    "commit": {
        "message": "Fix the bug",
        "author": {"name": "Octocat", "email": "octocat@github.com", "date": "2021-01-01T00:00:00Z"},
        "committer": {"name": "Octocat", "email": "octocat@github.com", "date": "2021-01-01T00:00:00Z"},
    },
}

SAMPLE_REVIEW = {
    "id": 55,
    "node_id": "PRR_kwDOxyz",
    "body": "Looks good",
    "state": "PENDING",
    "commit_id": "abc123",
    "submitted_at": None,
    "author_association": "COLLABORATOR",
    "user": SAMPLE_USER,
    "html_url": "https://github.com/octocat/Hello-World/pull/7#pullrequestreview-55",
}

GRAPHQL_PENDING_REVIEWS = {
    "data": {
        "repository": {
            "pullRequest": {
                "id": "PR_kwDOabc",
                "reviews": {"nodes": [{"id": "PRR_kwDOxyz", "databaseId": 55}]},
            }
        }
    }
}

GRAPHQL_ADD_THREAD = {
    "data": {
        "addPullRequestReviewThread": {
            "thread": {
                "id": "PRRT_kwDO1",
                "path": "src/main.py",
                "line": 12,
                "startLine": None,
                "diffSide": "RIGHT",
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "id": "PRRC_kwDO1",
                            "databaseId": 900,
                            "body": "Consider renaming this",
                            "url": "https://github.com/octocat/Hello-World/pull/7#discussion_r900",
                            "createdAt": "2021-01-03T00:00:00Z",
                            "author": {"login": "octocat", "avatarUrl": "https://github.com/octocat.png"},
                        }
                    ]
                },
            }
        }
    }
}


def _ok(data):
    return FetchResponse(status=200, headers={}, data=data)


class TestUpdatePullRequest:
    @pytest.mark.asyncio
    async def test_returns_updated_pull_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_PR)

        result = await github.execute_action("update_pull_request", {**REPO_ARGS, "title": "New title"}, mock_context)

        assert result.result.data["number"] == 7
        assert result.result.data["base"]["ref"] == "main"
        assert result.result.data["author"]["login"] == "octocat"
        assert result.result.data["url"] == "https://github.com/octocat/Hello-World/pull/7"

    @pytest.mark.asyncio
    async def test_request_uses_patch_and_sends_only_supplied_fields(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_PR)

        await github.execute_action(
            "update_pull_request", {**REPO_ARGS, "title": "New title", "state": "closed"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"
        assert mock_context.fetch.call_args.args[0].endswith("/repos/octocat/Hello-World/pulls/7")
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body == {"title": "New title", "state": "closed"}

    @pytest.mark.asyncio
    async def test_null_head_repo_is_tolerated(self, mock_context):
        deleted_fork = {**SAMPLE_PR, "head": {"ref": "feature-branch", "sha": "abc123", "repo": None}}
        mock_context.fetch.return_value = _ok(deleted_fork)

        result = await github.execute_action("update_pull_request", {**REPO_ARGS, "body": "hi"}, mock_context)

        assert result.result.data["head"]["repo"] is None

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("update_pull_request", {**REPO_ARGS, "title": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


class TestUpdatePullRequestBranch:
    @pytest.mark.asyncio
    async def test_returns_queued_message(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {"message": "Updating pull request branch.", "url": "https://api.github.com/repos/o/r/pulls/7"}
        )

        result = await github.execute_action("update_pull_request_branch", REPO_ARGS, mock_context)

        assert result.result.data["queued"] is True
        assert result.result.data["pull_number"] == 7
        assert result.result.data["message"] == "Updating pull request branch."

    @pytest.mark.asyncio
    async def test_request_uses_put_on_update_branch(self, mock_context):
        mock_context.fetch.return_value = _ok({"message": "Updating pull request branch."})

        await github.execute_action(
            "update_pull_request_branch", {**REPO_ARGS, "expected_head_sha": "abc123"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PUT"
        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/update-branch")
        assert mock_context.fetch.call_args.kwargs["json"] == {"expected_head_sha": "abc123"}


class TestGetPullRequestDiff:
    @pytest.mark.asyncio
    async def test_returns_diff_text(self, mock_context):
        diff_text = "diff --git a/src/main.py b/src/main.py\n@@ -1 +1,2 @@\n+import os\n"
        mock_context.fetch.return_value = _ok(diff_text)

        result = await github.execute_action("get_pull_request_diff", REPO_ARGS, mock_context)

        assert result.result.data["content"] == diff_text
        assert result.result.data["format"] == "diff"
        assert result.result.data["length"] == len(diff_text)

    @pytest.mark.asyncio
    async def test_requests_diff_media_type(self, mock_context):
        mock_context.fetch.return_value = _ok("diff text")

        await github.execute_action("get_pull_request_diff", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_args.kwargs["headers"]["Accept"] == "application/vnd.github.diff"

    @pytest.mark.asyncio
    async def test_patch_format_requests_patch_media_type(self, mock_context):
        mock_context.fetch.return_value = _ok("patch text")

        result = await github.execute_action("get_pull_request_diff", {**REPO_ARGS, "format": "patch"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["headers"]["Accept"] == "application/vnd.github.patch"
        assert result.result.data["format"] == "patch"

    @pytest.mark.asyncio
    async def test_unknown_format_is_rejected_before_the_request(self, mock_context):
        """The config enum catches a bad format at envelope validation, so no call is made."""
        mock_context.fetch.return_value = _ok("diff text")

        result = await github.execute_action("get_pull_request_diff", {**REPO_ARGS, "format": "json"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert mock_context.fetch.call_count == 0


class TestGetPullRequestFiles:
    @pytest.mark.asyncio
    async def test_returns_file_summaries(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_FILE])

        result = await github.execute_action("get_pull_request_files", REPO_ARGS, mock_context)

        assert len(result.result.data) == 1
        assert result.result.data[0]["filename"] == "src/main.py"
        assert result.result.data[0]["changes"] == 12
        assert result.result.data[0]["url"] == SAMPLE_FILE["blob_url"]
        assert result.result.data[0]["patch"].startswith("@@")

    @pytest.mark.asyncio
    async def test_include_patch_false_drops_patch(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_FILE])

        result = await github.execute_action(
            "get_pull_request_files", {**REPO_ARGS, "include_patch": False}, mock_context
        )

        assert result.result.data[0]["patch"] is None
        assert result.result.data[0]["additions"] == 10

    @pytest.mark.asyncio
    async def test_paginates_until_a_short_page(self, mock_context):
        full_page = [{**SAMPLE_FILE, "filename": f"src/file{i}.py"} for i in range(100)]
        mock_context.fetch.side_effect = [_ok(full_page), _ok([SAMPLE_FILE])]

        result = await github.execute_action("get_pull_request_files", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await github.execute_action("get_pull_request_files", REPO_ARGS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not Found" in result.result.message


class TestGetPullRequestStatus:
    @pytest.mark.asyncio
    async def test_rolls_up_statuses_for_the_head_commit(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PR), _ok(SAMPLE_COMBINED_STATUS)]

        result = await github.execute_action("get_pull_request_status", REPO_ARGS, mock_context)

        assert result.result.data["state"] == "success"
        assert result.result.data["sha"] == "abc123"
        assert result.result.data["total_count"] == 2
        assert [check["context"] for check in result.result.data["statuses"]] == ["ci/tests", "ci/lint"]

    @pytest.mark.asyncio
    async def test_second_request_targets_the_head_sha(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PR), _ok(SAMPLE_COMBINED_STATUS)]

        await github.execute_action("get_pull_request_status", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_count == 2
        assert mock_context.fetch.call_args_list[0].args[0].endswith("/pulls/7")
        assert mock_context.fetch.call_args_list[1].args[0].endswith("/commits/abc123/status")

    @pytest.mark.asyncio
    async def test_missing_head_sha_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_PR, "head": {}})

        result = await github.execute_action("get_pull_request_status", REPO_ARGS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "head commit SHA" in result.result.message


class TestGetPullRequestComments:
    @pytest.mark.asyncio
    async def test_returns_comment_summaries(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_REVIEW_COMMENT])

        result = await github.execute_action("get_pull_request_comments", REPO_ARGS, mock_context)

        assert len(result.result.data) == 1
        assert result.result.data[0]["path"] == "src/main.py"
        assert result.result.data[0]["line"] == 12
        assert result.result.data[0]["author"]["login"] == "octocat"
        assert result.result.data[0]["url"].endswith("#discussion_r900")

    @pytest.mark.asyncio
    async def test_sort_direction_and_since_are_forwarded(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_REVIEW_COMMENT])

        await github.execute_action(
            "get_pull_request_comments",
            {**REPO_ARGS, "sort": "updated", "direction": "desc", "since": "2021-01-01T00:00:00Z"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["sort"] == "updated"
        assert params["direction"] == "desc"
        assert params["since"] == "2021-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_deleted_author_is_tolerated(self, mock_context):
        mock_context.fetch.return_value = _ok([{**SAMPLE_REVIEW_COMMENT, "user": None}])

        result = await github.execute_action("get_pull_request_comments", REPO_ARGS, mock_context)

        assert result.result.data[0]["author"] is None


class TestAddReplyToPullRequestComment:
    @pytest.mark.asyncio
    async def test_returns_the_reply(self, mock_context):
        reply = {**SAMPLE_REVIEW_COMMENT, "id": 901, "in_reply_to_id": 900, "body": "Agreed"}
        mock_context.fetch.return_value = _ok(reply)

        result = await github.execute_action(
            "add_reply_to_pull_request_comment",
            {**REPO_ARGS, "comment_id": 900, "body": "Agreed"},
            mock_context,
        )

        assert result.result.data["id"] == 901
        assert result.result.data["in_reply_to_id"] == 900
        assert result.result.data["body"] == "Agreed"

    @pytest.mark.asyncio
    async def test_request_targets_the_replies_endpoint(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW_COMMENT)

        await github.execute_action(
            "add_reply_to_pull_request_comment",
            {**REPO_ARGS, "comment_id": 900, "body": "Agreed"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/comments/900/replies")
        assert mock_context.fetch.call_args.kwargs["json"] == {"body": "Agreed"}


class TestListPullRequestCommits:
    @pytest.mark.asyncio
    async def test_returns_commit_summaries(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_COMMIT])

        result = await github.execute_action("list_pull_request_commits", REPO_ARGS, mock_context)

        assert len(result.result.data) == 1
        assert result.result.data[0]["sha"] == "abc123"
        assert result.result.data[0]["message"] == "Fix the bug"
        assert result.result.data[0]["author"]["name"] == "Octocat"

    @pytest.mark.asyncio
    async def test_request_targets_the_pull_request_commits_endpoint(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_COMMIT])

        await github.execute_action("list_pull_request_commits", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/commits")

    @pytest.mark.asyncio
    async def test_paginates_until_a_short_page(self, mock_context):
        full_page = [{**SAMPLE_COMMIT, "sha": f"sha{i}"} for i in range(100)]
        mock_context.fetch.side_effect = [_ok(full_page), _ok([SAMPLE_COMMIT])]

        result = await github.execute_action("list_pull_request_commits", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101


class TestGetPullRequestReviews:
    @pytest.mark.asyncio
    async def test_returns_review_summaries(self, mock_context):
        submitted = {**SAMPLE_REVIEW, "state": "APPROVED", "submitted_at": "2021-01-03T00:00:00Z"}
        mock_context.fetch.return_value = _ok([submitted])

        result = await github.execute_action("get_pull_request_reviews", REPO_ARGS, mock_context)

        assert len(result.result.data) == 1
        assert result.result.data[0]["state"] == "APPROVED"
        assert result.result.data[0]["author"]["login"] == "octocat"
        assert result.result.data[0]["url"].endswith("#pullrequestreview-55")

    @pytest.mark.asyncio
    async def test_request_targets_the_reviews_endpoint(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_REVIEW])

        await github.execute_action("get_pull_request_reviews", REPO_ARGS, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/reviews")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad credentials")

        result = await github.execute_action("get_pull_request_reviews", REPO_ARGS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Bad credentials" in result.result.message


class TestCreatePendingPullRequestReview:
    @pytest.mark.asyncio
    async def test_returns_pending_review(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)

        result = await github.execute_action("create_pending_pull_request_review", REPO_ARGS, mock_context)

        assert result.result.data["id"] == 55
        assert result.result.data["state"] == "PENDING"
        assert result.result.data["submitted_at"] is None

    @pytest.mark.asyncio
    async def test_event_is_never_sent_so_the_review_stays_pending(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)

        await github.execute_action(
            "create_pending_pull_request_review",
            {**REPO_ARGS, "body": "Draft", "event": "APPROVE"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "event" not in body
        assert body["body"] == "Draft"

    @pytest.mark.asyncio
    async def test_inline_comments_are_forwarded(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)
        comments = [{"path": "src/main.py", "line": 12, "side": "RIGHT", "body": "Nit"}]

        await github.execute_action(
            "create_pending_pull_request_review",
            {**REPO_ARGS, "commit_id": "abc123", "comments": comments},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["comments"] == comments
        assert body["commit_id"] == "abc123"
        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/reviews")


class TestSubmitPendingPullRequestReview:
    @pytest.mark.asyncio
    async def test_returns_submitted_review(self, mock_context):
        submitted = {**SAMPLE_REVIEW, "state": "APPROVED", "submitted_at": "2021-01-03T00:00:00Z"}
        mock_context.fetch.return_value = _ok(submitted)

        result = await github.execute_action(
            "submit_pending_pull_request_review",
            {**REPO_ARGS, "review_id": 55, "event": "APPROVE"},
            mock_context,
        )

        assert result.result.data["state"] == "APPROVED"
        assert result.result.data["submitted_at"] == "2021-01-03T00:00:00Z"

    @pytest.mark.asyncio
    async def test_request_targets_the_events_endpoint(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)

        await github.execute_action(
            "submit_pending_pull_request_review",
            {**REPO_ARGS, "review_id": 55, "event": "REQUEST_CHANGES", "body": "Please fix"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/reviews/55/events")
        assert mock_context.fetch.call_args.kwargs["json"] == {"event": "REQUEST_CHANGES", "body": "Please fix"}


class TestDeletePendingPullRequestReview:
    @pytest.mark.asyncio
    async def test_returns_deleted_marker(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)

        result = await github.execute_action(
            "delete_pending_pull_request_review", {**REPO_ARGS, "review_id": 55}, mock_context
        )

        assert result.result.data["deleted"] is True
        assert result.result.data["review_id"] == 55
        assert result.result.data["state"] == "PENDING"

    @pytest.mark.asyncio
    async def test_request_uses_delete_on_the_review(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVIEW)

        await github.execute_action("delete_pending_pull_request_review", {**REPO_ARGS, "review_id": 55}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"
        assert mock_context.fetch.call_args.args[0].endswith("/pulls/7/reviews/55")


class TestAddCommentToPendingReview:
    @pytest.mark.asyncio
    async def test_resolves_the_review_then_adds_a_thread(self, mock_context):
        mock_context.fetch.side_effect = [_ok(GRAPHQL_PENDING_REVIEWS), _ok(GRAPHQL_ADD_THREAD)]

        result = await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Consider renaming this", "line": 12, "side": "RIGHT"},
            mock_context,
        )

        assert mock_context.fetch.call_count == 2
        assert result.result.data["thread_id"] == "PRRT_kwDO1"
        assert result.result.data["review_node_id"] == "PRR_kwDOxyz"
        assert result.result.data["comment"]["id"] == 900
        assert result.result.data["comment"]["author"]["login"] == "octocat"

    @pytest.mark.asyncio
    async def test_both_calls_go_to_the_graphql_endpoint(self, mock_context):
        mock_context.fetch.side_effect = [_ok(GRAPHQL_PENDING_REVIEWS), _ok(GRAPHQL_ADD_THREAD)]

        await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12},
            mock_context,
        )

        for call in mock_context.fetch.call_args_list:
            assert call.args[0] == "https://api.github.com/graphql"
            assert call.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_mutation_uses_add_pull_request_review_thread(self, mock_context):
        mock_context.fetch.side_effect = [_ok(GRAPHQL_PENDING_REVIEWS), _ok(GRAPHQL_ADD_THREAD)]

        await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12, "side": "RIGHT"},
            mock_context,
        )

        mutation = mock_context.fetch.call_args_list[1].kwargs["json"]
        assert "addPullRequestReviewThread" in mutation["query"]
        assert mutation["variables"]["reviewId"] == "PRR_kwDOxyz"
        assert mutation["variables"]["line"] == 12
        assert mutation["variables"]["side"] == "RIGHT"

    @pytest.mark.asyncio
    async def test_unset_optional_variables_are_omitted(self, mock_context):
        mock_context.fetch.side_effect = [_ok(GRAPHQL_PENDING_REVIEWS), _ok(GRAPHQL_ADD_THREAD)]

        await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Whole-file note", "subject_type": "FILE"},
            mock_context,
        )

        variables = mock_context.fetch.call_args_list[1].kwargs["json"]["variables"]
        assert variables["subjectType"] == "FILE"
        assert "line" not in variables
        assert "side" not in variables
        assert "startLine" not in variables

    @pytest.mark.asyncio
    async def test_review_id_selects_the_matching_draft(self, mock_context):
        two_drafts = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "id": "PR_kwDOabc",
                        "reviews": {
                            "nodes": [
                                {"id": "PRR_other", "databaseId": 11},
                                {"id": "PRR_kwDOxyz", "databaseId": 55},
                            ]
                        },
                    }
                }
            }
        }
        mock_context.fetch.side_effect = [_ok(two_drafts), _ok(GRAPHQL_ADD_THREAD)]

        await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12, "review_id": 55},
            mock_context,
        )

        assert mock_context.fetch.call_args_list[1].kwargs["json"]["variables"]["reviewId"] == "PRR_kwDOxyz"

    @pytest.mark.asyncio
    async def test_no_pending_review_returns_action_error(self, mock_context):
        empty = {"data": {"repository": {"pullRequest": {"id": "PR_kwDOabc", "reviews": {"nodes": []}}}}}
        mock_context.fetch.return_value = _ok(empty)

        result = await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No pending review found" in result.result.message

    @pytest.mark.asyncio
    async def test_unknown_review_id_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = _ok(GRAPHQL_PENDING_REVIEWS)

        result = await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12, "review_id": 99},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No pending review with id 99" in result.result.message

    @pytest.mark.asyncio
    async def test_graphql_errors_surface_as_action_error(self, mock_context):
        mock_context.fetch.return_value = _ok({"errors": [{"message": "Could not resolve to a node"}]})

        result = await github.execute_action(
            "add_comment_to_pending_review",
            {**REPO_ARGS, "path": "src/main.py", "body": "Nit", "line": 12},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Could not resolve to a node" in result.result.message
