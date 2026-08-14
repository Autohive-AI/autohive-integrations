import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from fifteenfive import (
    extract_error_message,
    fifteenfive,
    get_auth_headers,
    get_base_url,
)

pytestmark = pytest.mark.unit

# ---- Sample data ----

SAMPLE_USER = {
    "id": 1,
    "global_id": "11111111-1111-1111-1111-111111111111",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "is_active": True,
    "company_groups_ids": [10],
}

SAMPLE_GROUP = {"id": 10, "name": "Engineering", "group_type_name": "Departments", "members_count": 5}

SAMPLE_OBJECTIVE = {
    "id": 100,
    "description": "Ship the new dashboard",
    "scope": "individual",
    "state": "active",
    "color": "green",
    "percentage": 40,
}

SAMPLE_HIGH_FIVE = {
    "id": 200,
    "text": "Great work @Ada!",
    "creator_id": 1,
    "creator": "https://acme.15five.com/api/public/user/1/",
    "receivers": [{"id": 2, "url": "https://acme.15five.com/api/public/user/2/"}],
}

SAMPLE_CHECK_IN = {
    "id": 300,
    "user": "https://acme.15five.com/api/public/user/1/",
    "due_date": "2026-08-14",
    "questions": [],
    "comments": [],
}

SAMPLE_REVIEW_CYCLE = {"id": 400, "name": "H1 2026 Review", "status": "in_progress"}

SAMPLE_ONE_ON_ONE = {"id": 500, "user_1": "https://acme.15five.com/api/public/user/1/", "is_draft": False}


def paginated(results):
    return {"count": len(results), "next": None, "previous": None, "results": results}


# ---- Helper Functions ----


class TestGetBaseUrl:
    def test_builds_url_from_subdomain(self, mock_context):
        assert get_base_url(mock_context) == "https://acme.15five.com/api/public"

    def test_missing_subdomain_defaults_to_empty(self, mock_context):
        mock_context.auth["credentials"] = {}
        assert get_base_url(mock_context) == "https://.15five.com/api/public"


class TestGetAuthHeaders:
    def test_builds_bearer_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["Content-Type"] == "application/json"

    def test_missing_api_key_defaults_to_empty(self, mock_context):
        mock_context.auth["credentials"] = {}
        headers = get_auth_headers(mock_context)
        assert headers["Authorization"] == "Bearer "


class TestExtractErrorMessage:
    def test_extracts_detail_field(self):
        err = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})
        assert extract_error_message(err) == "Invalid token"

    def test_extracts_message_field(self):
        err = HTTPError(500, "Server Error", {"message": "Something went wrong"})
        assert extract_error_message(err) == "Something went wrong"

    def test_extracts_field_errors(self):
        err = HTTPError(400, "Bad Request", {"text": ["This field is required."]})
        assert extract_error_message(err) == "text: This field is required."

    def test_falls_back_to_status_and_message(self):
        err = HTTPError(502, "Bad Gateway", "not json")
        assert extract_error_message(err) == "15Five API error (HTTP 502): Bad Gateway"


# ---- list_users ----


class TestListUsers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_USER]))

        result = await fifteenfive.execute_action("list_users", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["users"] == [SAMPLE_USER]
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_users", {"email": "ada@example.com"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/user/"
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"email": "ada@example.com"}

    @pytest.mark.asyncio
    async def test_boolean_filter_serialized_as_lowercase_string(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_users", {"is_active": True}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"is_active": "true"}

    @pytest.mark.asyncio
    async def test_no_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        result = await fifteenfive.execute_action("list_users", {}, mock_context)

        assert result.result.data["users"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_users", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid token" in result.result.message


# ---- get_user ----


class TestGetUser:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        result = await fifteenfive.execute_action("get_user", {"user_id": 1}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["user"] == SAMPLE_USER

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        await fifteenfive.execute_action("get_user", {"user_id": 1}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/user/1/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_user", {"user_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found." in result.result.message


# ---- list_groups ----


class TestListGroups:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_GROUP]))

        result = await fifteenfive.execute_action("list_groups", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["groups"] == [SAMPLE_GROUP]

    @pytest.mark.asyncio
    async def test_request_url_and_name_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_groups", {"name__in": ["Engineering", "Sales"]}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/group/"
        assert call_args.kwargs["params"] == {"name__in": "Engineering,Sales"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"detail": "Forbidden"})

        result = await fifteenfive.execute_action("list_groups", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- list_objectives ----


class TestListObjectives:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_OBJECTIVE]))

        result = await fifteenfive.execute_action("list_objectives", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["objectives"] == [SAMPLE_OBJECTIVE]

    @pytest.mark.asyncio
    async def test_request_url_and_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action(
            "list_objectives", {"scope": "individual", "state": "active", "user_id": 1}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/"
        assert call_args.kwargs["params"] == {"scope": "individual", "state": "active", "user_id": 1}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"detail": "Bad request"})

        result = await fifteenfive.execute_action("list_objectives", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Bad request" in result.result.message


# ---- get_objective ----


class TestGetObjective:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_OBJECTIVE)

        result = await fifteenfive.execute_action("get_objective", {"objective_id": 100}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["objective"] == SAMPLE_OBJECTIVE

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_OBJECTIVE)

        await fifteenfive.execute_action("get_objective", {"objective_id": 100}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/100/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_objective", {"objective_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_high_fives ----


class TestListHighFives:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_HIGH_FIVE]))

        result = await fifteenfive.execute_action("list_high_fives", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["high_fives"] == [SAMPLE_HIGH_FIVE]

    @pytest.mark.asyncio
    async def test_request_url_and_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_high_fives", {"receiver_id": 2}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/high-five/"
        assert call_args.kwargs["params"] == {"receiver_id": 2}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(429, "Too Many Requests", {"detail": "Rate limited"})

        result = await fifteenfive.execute_action("list_high_fives", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Rate limited" in result.result.message


# ---- create_high_five ----


class TestCreateHighFive:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_HIGH_FIVE)

        result = await fifteenfive.execute_action(
            "create_high_five", {"text": "Great work @Ada!", "creator_id": 1}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["high_five"] == SAMPLE_HIGH_FIVE

    @pytest.mark.asyncio
    async def test_request_url_method_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_HIGH_FIVE)

        await fifteenfive.execute_action(
            "create_high_five", {"text": "Great work @Ada!", "creator_id": 1}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/high-five/"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"text": "Great work @Ada!", "creator_id": 1}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"creator_id": ["This field is required."]})

        result = await fifteenfive.execute_action("create_high_five", {"text": "Hi", "creator_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "creator_id" in result.result.message


# ---- list_reports ----


class TestListReports:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_CHECK_IN]))

        result = await fifteenfive.execute_action("list_reports", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["reports"] == [SAMPLE_CHECK_IN]

    @pytest.mark.asyncio
    async def test_request_url_and_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_reports", {"user_id": 1, "due_date_start": "2026-08-01"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/report/"
        assert call_args.kwargs["params"] == {"user_id": 1, "due_date_start": "2026-08-01"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "Server Error", "not json")

        result = await fifteenfive.execute_action("list_reports", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


# ---- get_report ----


class TestGetReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHECK_IN)

        result = await fifteenfive.execute_action("get_report", {"report_id": 300}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["report"] == SAMPLE_CHECK_IN

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHECK_IN)

        await fifteenfive.execute_action("get_report", {"report_id": 300}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/report/300/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_report", {"report_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_review_cycles ----


class TestListReviewCycles:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_REVIEW_CYCLE]))

        result = await fifteenfive.execute_action("list_review_cycles", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["review_cycles"] == [SAMPLE_REVIEW_CYCLE]

    @pytest.mark.asyncio
    async def test_request_url_and_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_review_cycles", {"started_on_start": "2026-01-01"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/"
        assert call_args.kwargs["params"] == {"started_on_start": "2026-01-01"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_review_cycles", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid token" in result.result.message


# ---- list_one_on_ones ----


class TestListOneOnOnes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_ONE_ON_ONE]))

        result = await fifteenfive.execute_action("list_one_on_ones", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["one_on_ones"] == [SAMPLE_ONE_ON_ONE]

    @pytest.mark.asyncio
    async def test_request_url_and_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action(
            "list_one_on_ones", {"user_id": 1, "is_draft": False, "type": "Manager-Reporter"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/one-on-one/"
        assert call_args.kwargs["params"] == {"user_id": 1, "is_draft": "false", "type": "Manager-Reporter"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"detail": "Forbidden"})

        result = await fifteenfive.execute_action("list_one_on_ones", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- get_one_on_one ----


class TestGetOneOnOne:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ONE_ON_ONE)

        result = await fifteenfive.execute_action("get_one_on_one", {"one_on_one_id": 500}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["one_on_one"] == SAMPLE_ONE_ON_ONE

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ONE_ON_ONE)

        await fifteenfive.execute_action("get_one_on_one", {"one_on_one_id": 500}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/one-on-one/500/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_one_on_one", {"one_on_one_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_group ----


class TestGetGroup:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_GROUP)

        result = await fifteenfive.execute_action("get_group", {"group_id": 10}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["group"] == SAMPLE_GROUP

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_GROUP)

        await fifteenfive.execute_action("get_group", {"group_id": 10}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/group/10/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_group", {"group_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_group_types / get_group_type ----

SAMPLE_GROUP_TYPE = {"id": 20, "name_plural": "Departments", "name_singular": "Department"}


class TestListGroupTypes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_GROUP_TYPE]))

        result = await fifteenfive.execute_action("list_group_types", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["group_types"] == [SAMPLE_GROUP_TYPE]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_group_types", {"name_plural": "Departments"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/group-type/"
        assert call_args.kwargs["params"] == {"name_plural": "Departments"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_group_types", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetGroupType:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_GROUP_TYPE)

        result = await fifteenfive.execute_action("get_group_type", {"group_type_id": 20}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["group_type"] == SAMPLE_GROUP_TYPE

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_GROUP_TYPE)

        await fifteenfive.execute_action("get_group_type", {"group_type_id": 20}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/group-type/20/"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_group_type", {"group_type_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_departments / get_department ----

SAMPLE_DEPARTMENT = {"id": 30, "name": "Engineering"}


class TestListDepartments:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_DEPARTMENT]))

        result = await fifteenfive.execute_action("list_departments", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["departments"] == [SAMPLE_DEPARTMENT]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_departments", {"name": "Engineering"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/department/"
        assert call_args.kwargs["params"] == {"name": "Engineering"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_departments", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDepartment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_DEPARTMENT)

        result = await fifteenfive.execute_action("get_department", {"department_id": 30}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["department"] == SAMPLE_DEPARTMENT

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_DEPARTMENT)

        await fifteenfive.execute_action("get_department", {"department_id": 30}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/department/30/"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_department", {"department_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_feature_status ----


class TestGetFeatureStatus:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"pulse": True, "demographic_attributes": False}
        )

        result = await fifteenfive.execute_action("get_feature_status", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["feature_status"] == {"pulse": True, "demographic_attributes": False}

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await fifteenfive.execute_action("get_feature_status", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/feature-status/"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("get_feature_status", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- People Attributes ----

SAMPLE_ATTRIBUTE = {"id": 40, "name": "T-Shirt Size", "slug": "t-shirt-size", "datatype": "text"}
SAMPLE_ATTRIBUTE_VALUE = {"id": 50, "value": "L", "user": 1, "attribute": 40}


class TestListAttributes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_ATTRIBUTE]))

        result = await fifteenfive.execute_action("list_attributes", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["attributes"] == [SAMPLE_ATTRIBUTE]

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_attributes", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/attribute/"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_attributes", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAttribute:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ATTRIBUTE)

        result = await fifteenfive.execute_action("get_attribute", {"attribute_id": 40}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute"] == SAMPLE_ATTRIBUTE

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_attribute", {"attribute_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateAttribute:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ATTRIBUTE)

        result = await fifteenfive.execute_action(
            "create_attribute", {"name": "T-Shirt Size", "datatype": "text"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute"] == SAMPLE_ATTRIBUTE

    @pytest.mark.asyncio
    async def test_request_url_method_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ATTRIBUTE)

        await fifteenfive.execute_action("create_attribute", {"name": "T-Shirt Size", "datatype": "text"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/attribute/"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"name": "T-Shirt Size", "datatype": "text"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"name": ["This field is required."]})

        result = await fifteenfive.execute_action("create_attribute", {"name": "", "datatype": "text"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAttributeValues:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=paginated([SAMPLE_ATTRIBUTE_VALUE])
        )

        result = await fifteenfive.execute_action("list_attribute_values", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute_values"] == [SAMPLE_ATTRIBUTE_VALUE]

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_attribute_values", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAttributeValue:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ATTRIBUTE_VALUE)

        result = await fifteenfive.execute_action("get_attribute_value", {"attribute_value_id": 50}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute_value"] == SAMPLE_ATTRIBUTE_VALUE

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_attribute_value", {"attribute_value_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateAttributeValue:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ATTRIBUTE_VALUE)

        result = await fifteenfive.execute_action(
            "create_attribute_value", {"name": "T-Shirt Size", "value": "L", "user_id": 1}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute_value"] == SAMPLE_ATTRIBUTE_VALUE

    @pytest.mark.asyncio
    async def test_request_payload_includes_optional_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ATTRIBUTE_VALUE)

        await fifteenfive.execute_action(
            "create_attribute_value", {"name": "T-Shirt Size", "value": "L", "user_id": 1}, mock_context
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload == {"name": "T-Shirt Size", "value": "L", "user_id": 1}

    @pytest.mark.asyncio
    async def test_request_payload_omits_user_id_when_not_given(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ATTRIBUTE_VALUE)

        await fifteenfive.execute_action("create_attribute_value", {"name": "T-Shirt Size", "value": "L"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload == {"name": "T-Shirt Size", "value": "L"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"name": ["This field is required."]})

        result = await fifteenfive.execute_action("create_attribute_value", {"name": "", "value": "L"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- create_objectives ----


class TestCreateObjectives:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        created = [{**SAMPLE_OBJECTIVE, "id": 101}]
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=created)

        result = await fifteenfive.execute_action(
            "create_objectives",
            {
                "objectives": [
                    {
                        "description": "Ship the new dashboard",
                        "start_ts": "2026-01-01",
                        "end_ts": "2026-03-31",
                        "scope": "individual",
                        "user_id": 1,
                    }
                ]
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["objectives"] == created

    @pytest.mark.asyncio
    async def test_request_url_method_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=[])

        objectives = [
            {
                "description": "Ship the new dashboard",
                "start_ts": "2026-01-01",
                "end_ts": "2026-03-31",
                "scope": "individual",
                "user_id": 1,
            }
        ]
        await fifteenfive.execute_action("create_objectives", {"objectives": objectives}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == objectives

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"description": ["This field is required."]})

        objectives = [
            {"description": "X", "start_ts": "2026-01-01", "end_ts": "2026-03-31", "scope": "individual", "user_id": 1}
        ]
        result = await fifteenfive.execute_action("create_objectives", {"objectives": objectives}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_objective_history / get_objective_history ----

SAMPLE_HISTORY_EVENT = {"objective_id": 100, "event": "updated", "user": "https://acme.15five.com/api/public/user/1/"}


class TestListObjectiveHistory:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_HISTORY_EVENT]))

        result = await fifteenfive.execute_action("list_objective_history", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["history"] == [SAMPLE_HISTORY_EVENT]

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_objective_history", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/history/"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_objective_history", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetObjectiveHistory:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_HISTORY_EVENT])

        result = await fifteenfive.execute_action("get_objective_history", {"objective_id": 100}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["history"] == [SAMPLE_HISTORY_EVENT]

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await fifteenfive.execute_action("get_objective_history", {"objective_id": 100}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/100/history/"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_objective_history", {"objective_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_key_results ----


class TestListKeyResults:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        key_results = [{"id": 1, "description": "Hit 100 signups", "type": "number"}]
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={**SAMPLE_OBJECTIVE, "key_results": key_results}
        )

        result = await fifteenfive.execute_action("list_key_results", {"objective_id": 100}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["key_results"] == key_results

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_OBJECTIVE)

        await fifteenfive.execute_action("list_key_results", {"objective_id": 100}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/objective/100/"

    @pytest.mark.asyncio
    async def test_objective_without_key_results_returns_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_OBJECTIVE)

        result = await fifteenfive.execute_action("list_key_results", {"objective_id": 100}, mock_context)

        assert result.result.data["key_results"] == []

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("list_key_results", {"objective_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_high_five ----


class TestGetHighFive:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_HIGH_FIVE)

        result = await fifteenfive.execute_action("get_high_five", {"high_five_id": 200}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["high_five"] == SAMPLE_HIGH_FIVE

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_HIGH_FIVE)

        await fifteenfive.execute_action("get_high_five", {"high_five_id": 200}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/high-five/200/"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_high_five", {"high_five_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_answers / get_answer ----

SAMPLE_ANSWER = {"id": 600, "report_id": 300, "question": 1, "user": 1, "answer_text": "Great week!"}


class TestListAnswers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_ANSWER]))

        result = await fifteenfive.execute_action("list_answers", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["answers"] == [SAMPLE_ANSWER]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_answers", {"question_id": 1}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/answer/"
        assert call_args.kwargs["params"] == {"question_id": 1}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_answers", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAnswer:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ANSWER)

        result = await fifteenfive.execute_action("get_answer", {"answer_id": 600}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["answer"] == SAMPLE_ANSWER

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_answer", {"answer_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_questions / get_question ----

SAMPLE_QUESTION = {"id": 700, "question_text": "What went well this week?", "question_type": "text"}


class TestListQuestions:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_QUESTION]))

        result = await fifteenfive.execute_action("list_questions", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["questions"] == [SAMPLE_QUESTION]

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_questions", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetQuestion:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_QUESTION)

        result = await fifteenfive.execute_action("get_question", {"question_id": 700}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["question"] == SAMPLE_QUESTION

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_question", {"question_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_priorities / create_priorities ----

SAMPLE_PRIORITY = {"id": 800, "user_id": 1, "manager_id": 2, "text": "Ship v2", "status": "on_track"}


class TestListPriorities:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PRIORITY])

        result = await fifteenfive.execute_action("list_priorities", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["priorities"] == [SAMPLE_PRIORITY]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await fifteenfive.execute_action("list_priorities", {"user_id": 1, "include_past_checkins": True}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/priority/"
        assert call_args.kwargs["params"] == {"user_id": 1, "include_past_checkins": "true"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_priorities", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreatePriorities:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=[SAMPLE_PRIORITY])

        result = await fifteenfive.execute_action(
            "create_priorities", {"priorities": [{"user_id": 1, "text": "Ship v2"}]}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["priorities"] == [SAMPLE_PRIORITY]

    @pytest.mark.asyncio
    async def test_request_url_method_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=[])

        priorities = [{"user_id": 1, "text": "Ship v2"}]
        await fifteenfive.execute_action("create_priorities", {"priorities": priorities}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/priority/"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == priorities

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"text": ["This field is required."]})

        result = await fifteenfive.execute_action(
            "create_priorities", {"priorities": [{"user_id": 1, "text": "Ship v2"}]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- list_pulses / get_pulse ----

SAMPLE_PULSE = {"id": 900, "report": 300, "user": 1, "value": 4}


class TestListPulses:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_PULSE]))

        result = await fifteenfive.execute_action("list_pulses", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["pulses"] == [SAMPLE_PULSE]

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_pulses", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetPulse:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PULSE)

        result = await fifteenfive.execute_action("get_pulse", {"pulse_id": 900}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["pulse"] == SAMPLE_PULSE

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_pulse", {"pulse_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_review_cycle ----


class TestGetReviewCycle:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_REVIEW_CYCLE)

        result = await fifteenfive.execute_action("get_review_cycle", {"review_cycle_id": 400}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["review_cycle"] == SAMPLE_REVIEW_CYCLE

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_REVIEW_CYCLE)

        await fifteenfive.execute_action("get_review_cycle", {"review_cycle_id": 400}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/400/"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("get_review_cycle", {"review_cycle_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_review_cycle_participants ----

SAMPLE_PARTICIPANT = {"id": 1, "user": 1, "manager": 2}


class TestListReviewCycleParticipants:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_PARTICIPANT]))

        result = await fifteenfive.execute_action(
            "list_review_cycle_participants", {"review_cycle_id": 400}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["participants"] == [SAMPLE_PARTICIPANT]

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_review_cycle_participants", {"review_cycle_id": 400}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/400/participants/"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action(
            "list_review_cycle_participants", {"review_cycle_id": 999}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- list_review_cycle_results_answers ----


class TestListReviewCycleResultsAnswers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        results = {"participants": [], "authors": []}
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"count": 0, "next": None, "previous": None, "results": results}
        )

        result = await fifteenfive.execute_action(
            "list_review_cycle_results_answers", {"review_cycle_id": 400}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["results"] == results

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"count": 0, "next": None, "previous": None, "results": {}}
        )

        await fifteenfive.execute_action("list_review_cycle_results_answers", {"review_cycle_id": 400}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/400/results/answers/"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action(
            "list_review_cycle_results_answers", {"review_cycle_id": 999}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- list_review_cycle_results_performance_measurements ----

SAMPLE_MEASUREMENT = {"id": 1, "user_id": 1, "manager_id": 2, "measurements": []}


class TestListReviewCycleResultsPerformanceMeasurements:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_MEASUREMENT]))

        result = await fifteenfive.execute_action(
            "list_review_cycle_results_performance_measurements", {"review_cycle_id": 400}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["performance_measurements"] == [SAMPLE_MEASUREMENT]

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action(
            "list_review_cycle_results_performance_measurements", {"review_cycle_id": 400}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert (
            call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/400/results/performance-measurements/"
        )

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action(
            "list_review_cycle_results_performance_measurements", {"review_cycle_id": 999}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- list_reviews ----

SAMPLE_REVIEW = {"id": 1000, "review_type": "self", "user": 1, "status": "complete"}


class TestListReviews:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_REVIEW]))

        result = await fifteenfive.execute_action("list_reviews", {"review_cycle_id": 400}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["reviews"] == [SAMPLE_REVIEW]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_reviews", {"review_cycle_id": 400, "is_complete": True}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/review-cycle/400/reviews/"
        assert call_args.kwargs["params"] == {"is_complete": "true"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"detail": "Not found."})

        result = await fifteenfive.execute_action("list_reviews", {"review_cycle_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_vacations ----

SAMPLE_VACATION = {"id": 1100, "note": "Summer break", "start_dt": "2026-07-01", "end_dt": "2026-07-10", "user": 1}


class TestListVacations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_VACATION]))

        result = await fifteenfive.execute_action("list_vacations", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["vacations"] == [SAMPLE_VACATION]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_vacations", {"user": [1, 2]}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/vacation/"
        assert call_args.kwargs["params"] == {"user": "1,2"}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_vacations", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_security_audit ----

SAMPLE_AUDIT_EVENT = {"actor": 1, "create_ts": "2026-08-01T00:00:00Z", "type": "login", "extra": {}}


class TestListSecurityAudit:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([SAMPLE_AUDIT_EVENT]))

        result = await fifteenfive.execute_action("list_security_audit", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["events"] == [SAMPLE_AUDIT_EVENT]

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=paginated([]))

        await fifteenfive.execute_action("list_security_audit", {"actor_id": 1}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://acme.15five.com/api/public/security-audit/"
        assert call_args.kwargs["params"] == {"actor_id": 1}

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthorized", {"detail": "Invalid token"})

        result = await fifteenfive.execute_action("list_security_audit", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
