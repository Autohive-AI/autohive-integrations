import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import jobadder


pytestmark = pytest.mark.unit


class TestListJobAds:
    async def test_preserves_ad_state_dates_and_pagination(self, mock_context):
        ads = [
            {
                "adId": 42,
                "title": "Recruitment Coordinator",
                "state": "Posted",
                "postAt": "2026-11-02T00:00:00Z",
                "expireAt": "2026-12-02T00:00:00Z",
            },
            {"adId": 43, "title": "Office Manager", "state": "Draft", "expireAt": None},
        ]
        links = {"next": "https://au-api.jobadder.com/v2/jobads?offset=6&limit=2"}
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"items": ads, "totalCount": 9, "links": links}
        )

        result = await jobadder.execute_action("list_job_ads", {"offset": 4, "limit": 2}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"job_ads": ads, "total_count": 9, "links": links}
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/jobads", method="GET", params={"offset": 4, "limit": 2}
        )

    @pytest.mark.parametrize(("inputs", "sent_limit", "total"), [({}, 100, 0), ({"limit": 0}, 0, 12)])
    async def test_empty_and_count_only_responses(self, mock_context, inputs, sent_limit, total):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"totalCount": total})

        result = await jobadder.execute_action("list_job_ads", inputs, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"job_ads": [], "total_count": total, "links": {}}
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/jobads", method="GET", params={"offset": 0, "limit": sent_limit}
        )

    async def test_permission_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Job ad access denied")

        result = await jobadder.execute_action("list_job_ads", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Job ad access denied" in result.result.message


class TestGetJobAd:
    @pytest.mark.parametrize("description", ["<p>Applications close on 2 December.</p>", None])
    async def test_returns_provider_ad_details(self, mock_context, description):
        ad = {
            "adId": 42,
            "title": "Recruitment Coordinator",
            "summary": "Join our recruitment team.",
            "bulletPoints": ["Full time"],
            "description": description,
            "expireAt": "2026-12-02T00:00:00Z",
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ad)

        result = await jobadder.execute_action("get_job_ad", {"ad_id": 42}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"job_ad": ad}
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/jobads/42", method="GET")

    @pytest.mark.parametrize("inputs", [{}, {"ad_id": 0}])
    async def test_requires_a_positive_ad_id(self, mock_context, inputs):
        result = await jobadder.execute_action("get_job_ad", inputs, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    async def test_missing_ad_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Job ad not found")

        result = await jobadder.execute_action("get_job_ad", {"ad_id": 42}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Job ad not found" in result.result.message
