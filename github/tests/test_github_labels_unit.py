import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

SAMPLE_LABEL = {
    "id": 208045946,
    "node_id": "MDU6TGFiZWwyMDgwNDU5NDY=",
    "url": "https://api.github.com/repos/octocat/Hello-World/labels/bug",
    "name": "bug",
    "description": "Something isn't working",
    "color": "d73a4a",
    "default": True,
}

SAMPLE_LABEL_WITH_SPACES = {
    **SAMPLE_LABEL,
    "id": 208045947,
    "name": "good first issue",
    "url": "https://api.github.com/repos/octocat/Hello-World/labels/good%20first%20issue",
}

REPO_INPUTS = {"owner": "octocat", "repo": "Hello-World"}


def _label(index: int) -> dict:
    """Build a distinct label payload for pagination tests."""
    return {**SAMPLE_LABEL, "id": index, "name": f"label-{index}"}


class TestListLabels:
    @pytest.mark.asyncio
    async def test_returns_shaped_labels(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_LABEL])

        result = await github.execute_action("list_labels", dict(REPO_INPUTS), mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data) == 1
        label = result.result.data[0]
        assert label["name"] == "bug"
        assert label["color"] == "d73a4a"
        assert label["default"] is True
        assert label["url"] == SAMPLE_LABEL["url"]

    @pytest.mark.asyncio
    async def test_request_targets_repo_labels_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_LABEL])

        await github.execute_action("list_labels", dict(REPO_INPUTS), mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/repos/octocat/Hello-World/labels")

    @pytest.mark.asyncio
    async def test_follows_pagination_until_short_page(self, mock_context):
        first_page = [_label(index) for index in range(100)]
        second_page = [_label(100)]
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=first_page),
            FetchResponse(status=200, headers={}, data=second_page),
        ]

        result = await github.execute_action("list_labels", dict(REPO_INPUTS), mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101
        assert result.result.data[-1]["name"] == "label-100"

    @pytest.mark.asyncio
    async def test_limit_caps_returned_labels(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[_label(index) for index in range(5)]
        )

        result = await github.execute_action("list_labels", {**REPO_INPUTS, "limit": 2}, mock_context)

        assert len(result.result.data) == 2


class TestListIssueLabels:
    @pytest.mark.asyncio
    async def test_returns_shaped_labels(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_LABEL])

        result = await github.execute_action("list_issue_labels", {**REPO_INPUTS, "issue_number": 42}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data[0]["name"] == "bug"

    @pytest.mark.asyncio
    async def test_request_targets_issue_labels_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_LABEL])

        await github.execute_action("list_issue_labels", {**REPO_INPUTS, "issue_number": 42}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/repos/octocat/Hello-World/issues/42/labels")


class TestGetLabel:
    @pytest.mark.asyncio
    async def test_returns_shaped_label(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_LABEL)

        result = await github.execute_action("get_label", {**REPO_INPUTS, "name": "bug"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == SAMPLE_LABEL["id"]
        assert result.result.data["description"] == "Something isn't working"

    @pytest.mark.asyncio
    async def test_percent_encodes_label_name_in_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_LABEL_WITH_SPACES)

        await github.execute_action("get_label", {**REPO_INPUTS, "name": "good first issue"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/labels/good%20first%20issue")

    @pytest.mark.asyncio
    async def test_percent_encodes_slash_in_label_name(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_LABEL)

        await github.execute_action("get_label", {**REPO_INPUTS, "name": "area/api"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/labels/area%2Fapi")


class TestCreateLabel:
    @pytest.mark.asyncio
    async def test_returns_created_label(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LABEL)

        result = await github.execute_action(
            "create_label",
            {**REPO_INPUTS, "name": "bug", "color": "d73a4a", "description": "Something isn't working"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["name"] == "bug"

    @pytest.mark.asyncio
    async def test_posts_name_color_and_description(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LABEL)

        await github.execute_action(
            "create_label",
            {**REPO_INPUTS, "name": "bug", "color": "d73a4a", "description": "Broken"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/repos/octocat/Hello-World/labels")
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "name": "bug",
            "color": "d73a4a",
            "description": "Broken",
        }

    @pytest.mark.asyncio
    async def test_strips_leading_hash_from_color(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LABEL)

        await github.execute_action("create_label", {**REPO_INPUTS, "name": "bug", "color": "#d73a4a"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"]["color"] == "d73a4a"

    @pytest.mark.asyncio
    async def test_omits_unset_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LABEL)

        await github.execute_action("create_label", {**REPO_INPUTS, "name": "bug"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "bug"}


class TestUpdateLabel:
    @pytest.mark.asyncio
    async def test_returns_updated_label(self, mock_context):
        renamed = {**SAMPLE_LABEL, "name": "defect"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=renamed)

        result = await github.execute_action(
            "update_label", {**REPO_INPUTS, "name": "bug", "new_name": "defect"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["name"] == "defect"

    @pytest.mark.asyncio
    async def test_patches_with_new_name_against_encoded_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_LABEL)

        await github.execute_action(
            "update_label",
            {**REPO_INPUTS, "name": "good first issue", "new_name": "starter", "color": "#ffffff"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"
        assert mock_context.fetch.call_args.args[0].endswith("/labels/good%20first%20issue")
        assert mock_context.fetch.call_args.kwargs["json"] == {"new_name": "starter", "color": "ffffff"}


class TestDeleteLabel:
    @pytest.mark.asyncio
    async def test_returns_deleted_marker(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action("delete_label", {**REPO_INPUTS, "name": "bug"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"deleted": True, "name": "bug"}

    @pytest.mark.asyncio
    async def test_request_uses_delete_on_encoded_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await github.execute_action("delete_label", {**REPO_INPUTS, "name": "area/api"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"
        assert mock_context.fetch.call_args.args[0].endswith("/labels/area%2Fapi")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("delete_label", {**REPO_INPUTS, "name": "bug"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


class TestLabelErrorHandling:
    @pytest.mark.asyncio
    async def test_get_label_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await github.execute_action("get_label", {**REPO_INPUTS, "name": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not Found" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_token_returns_action_error(self, mock_context):
        mock_context.auth = {"auth_type": "PlatformOauth2", "credentials": {}}

        result = await github.execute_action("list_labels", dict(REPO_INPUTS), mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "authentication failed" in result.result.message
