"""
End-to-end integration tests for the 15Five integration.

These tests call the real 15Five Public API and require a valid API access
token and company subdomain, set via FIFTEENFIVE_API_KEY and
FIFTEENFIVE_SUBDOMAIN (in .env or exported).

Run (read-only, safe):
    pytest 15five/tests/test_fifteenfive_integration.py -m "integration and not destructive"

Run destructive tests (posts a real High Five, custom people attribute/value,
objective, or priority — only run deliberately, never by reviewers):
    pytest 15five/tests/test_fifteenfive_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from fifteenfive import fifteenfive

pytestmark = pytest.mark.integration

TEST_CREATOR_ID = os.environ.get("FIFTEENFIVE_TEST_CREATOR_ID", "")


def require_creator_id():
    if not TEST_CREATOR_ID:
        pytest.skip("FIFTEENFIVE_TEST_CREATOR_ID not set")


@pytest.fixture
def live_context(env_credentials):
    subdomain = env_credentials("FIFTEENFIVE_SUBDOMAIN")
    api_key = env_credentials("FIFTEENFIVE_API_KEY")
    if not subdomain or not api_key:
        pytest.skip("FIFTEENFIVE_SUBDOMAIN / FIFTEENFIVE_API_KEY not set — skipping integration tests")

    import aiohttp
    from unittest.mock import AsyncMock, MagicMock

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {"subdomain": subdomain, "api_key": api_key},
    }
    return ctx


# ---- Users ----


class TestListUsers:
    async def test_returns_users(self, live_context):
        result = await fifteenfive.execute_action("list_users", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "users" in result.result.data
        assert isinstance(result.result.data["users"], list)


class TestGetUser:
    async def test_fetches_a_real_user(self, live_context):
        list_result = await fifteenfive.execute_action("list_users", {"page": 1}, live_context)
        users = list_result.result.data["users"]
        if not users:
            pytest.skip("No users in account to test with")

        user_id = users[0]["id"]
        result = await fifteenfive.execute_action("get_user", {"user_id": user_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["user"]["id"] == user_id

    async def test_nonexistent_user_returns_action_error(self, live_context):
        result = await fifteenfive.execute_action("get_user", {"user_id": 0}, live_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Groups, Group Types & Departments ----


class TestListGroups:
    async def test_returns_groups(self, live_context):
        result = await fifteenfive.execute_action("list_groups", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "groups" in result.result.data


class TestGetGroup:
    async def test_fetches_a_real_group(self, live_context):
        list_result = await fifteenfive.execute_action("list_groups", {}, live_context)
        groups = list_result.result.data["groups"]
        if not groups:
            pytest.skip("No groups in account to test with")

        group_id = groups[0]["id"]
        result = await fifteenfive.execute_action("get_group", {"group_id": group_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["group"]["id"] == group_id


class TestListGroupTypes:
    async def test_returns_group_types(self, live_context):
        result = await fifteenfive.execute_action("list_group_types", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "group_types" in result.result.data


class TestGetGroupType:
    async def test_fetches_a_real_group_type(self, live_context):
        list_result = await fifteenfive.execute_action("list_group_types", {}, live_context)
        group_types = list_result.result.data["group_types"]
        if not group_types:
            pytest.skip("No group types in account to test with")

        group_type_id = group_types[0]["id"]
        result = await fifteenfive.execute_action("get_group_type", {"group_type_id": group_type_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["group_type"]["id"] == group_type_id


class TestListDepartments:
    async def test_returns_departments(self, live_context):
        result = await fifteenfive.execute_action("list_departments", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "departments" in result.result.data


class TestGetDepartment:
    async def test_fetches_a_real_department(self, live_context):
        list_result = await fifteenfive.execute_action("list_departments", {}, live_context)
        departments = list_result.result.data["departments"]
        if not departments:
            pytest.skip("No departments in account to test with")

        department_id = departments[0]["id"]
        result = await fifteenfive.execute_action("get_department", {"department_id": department_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["department"]["id"] == department_id


# ---- Feature Status ----


class TestGetFeatureStatus:
    async def test_returns_feature_status(self, live_context):
        result = await fifteenfive.execute_action("get_feature_status", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "feature_status" in result.result.data


# ---- People Attributes ----


class TestListAttributes:
    async def test_returns_attributes(self, live_context):
        result = await fifteenfive.execute_action("list_attributes", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "attributes" in result.result.data


class TestGetAttribute:
    async def test_fetches_a_real_attribute(self, live_context):
        list_result = await fifteenfive.execute_action("list_attributes", {}, live_context)
        attributes = list_result.result.data["attributes"]
        if not attributes:
            pytest.skip("No people attributes in account to test with")

        attribute_id = attributes[0]["id"]
        result = await fifteenfive.execute_action("get_attribute", {"attribute_id": attribute_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute"]["id"] == attribute_id


class TestListAttributeValues:
    async def test_returns_attribute_values(self, live_context):
        result = await fifteenfive.execute_action("list_attribute_values", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "attribute_values" in result.result.data


class TestGetAttributeValue:
    async def test_fetches_a_real_attribute_value(self, live_context):
        list_result = await fifteenfive.execute_action("list_attribute_values", {}, live_context)
        values = list_result.result.data["attribute_values"]
        if not values:
            pytest.skip("No people attribute values in account to test with")

        attribute_value_id = values[0]["id"]
        result = await fifteenfive.execute_action(
            "get_attribute_value", {"attribute_value_id": attribute_value_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["attribute_value"]["id"] == attribute_value_id


# ---- Objectives ----


class TestListObjectives:
    async def test_returns_objectives(self, live_context):
        result = await fifteenfive.execute_action("list_objectives", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "objectives" in result.result.data


class TestGetObjective:
    async def test_fetches_a_real_objective(self, live_context):
        list_result = await fifteenfive.execute_action("list_objectives", {"page": 1}, live_context)
        objectives = list_result.result.data["objectives"]
        if not objectives:
            pytest.skip("No objectives in account to test with")

        objective_id = objectives[0]["id"]
        result = await fifteenfive.execute_action("get_objective", {"objective_id": objective_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["objective"]["id"] == objective_id


class TestListObjectiveHistory:
    async def test_returns_history(self, live_context):
        result = await fifteenfive.execute_action("list_objective_history", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "history" in result.result.data


class TestGetObjectiveHistory:
    async def test_fetches_history_for_a_real_objective(self, live_context):
        list_result = await fifteenfive.execute_action("list_objectives", {"page": 1}, live_context)
        objectives = list_result.result.data["objectives"]
        if not objectives:
            pytest.skip("No objectives in account to test with")

        objective_id = objectives[0]["id"]
        result = await fifteenfive.execute_action("get_objective_history", {"objective_id": objective_id}, live_context)

        assert result.type == ResultType.ACTION
        assert "history" in result.result.data


class TestListKeyResults:
    async def test_fetches_key_results_for_a_real_objective(self, live_context):
        list_result = await fifteenfive.execute_action("list_objectives", {"page": 1}, live_context)
        objectives = list_result.result.data["objectives"]
        if not objectives:
            pytest.skip("No objectives in account to test with")

        objective_id = objectives[0]["id"]
        result = await fifteenfive.execute_action("list_key_results", {"objective_id": objective_id}, live_context)

        assert result.type == ResultType.ACTION
        assert "key_results" in result.result.data


# ---- High Fives ----


class TestListHighFives:
    async def test_returns_high_fives(self, live_context):
        result = await fifteenfive.execute_action("list_high_fives", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "high_fives" in result.result.data


class TestGetHighFive:
    async def test_fetches_a_real_high_five(self, live_context):
        list_result = await fifteenfive.execute_action("list_high_fives", {"page": 1}, live_context)
        high_fives = list_result.result.data["high_fives"]
        if not high_fives:
            pytest.skip("No high fives in account to test with")

        high_five_id = high_fives[0]["id"]
        result = await fifteenfive.execute_action("get_high_five", {"high_five_id": high_five_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["high_five"]["id"] == high_five_id


# ---- Check-in Reports, Answers & Questions ----


class TestListReports:
    async def test_returns_reports(self, live_context):
        result = await fifteenfive.execute_action("list_reports", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "reports" in result.result.data


class TestGetReport:
    async def test_fetches_a_real_report(self, live_context):
        list_result = await fifteenfive.execute_action("list_reports", {"page": 1}, live_context)
        reports = list_result.result.data["reports"]
        if not reports:
            pytest.skip("No check-in reports in account to test with")

        report_id = reports[0]["id"]
        result = await fifteenfive.execute_action("get_report", {"report_id": report_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["report"]["id"] == report_id


class TestListAnswers:
    async def test_returns_answers(self, live_context):
        result = await fifteenfive.execute_action("list_answers", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "answers" in result.result.data


class TestGetAnswer:
    async def test_fetches_a_real_answer(self, live_context):
        list_result = await fifteenfive.execute_action("list_answers", {"page": 1}, live_context)
        answers = list_result.result.data["answers"]
        if not answers:
            pytest.skip("No answers in account to test with")

        answer_id = answers[0]["id"]
        result = await fifteenfive.execute_action("get_answer", {"answer_id": answer_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["answer"]["id"] == answer_id


class TestListQuestions:
    async def test_returns_questions(self, live_context):
        result = await fifteenfive.execute_action("list_questions", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "questions" in result.result.data


class TestGetQuestion:
    async def test_fetches_a_real_question(self, live_context):
        list_result = await fifteenfive.execute_action("list_questions", {"page": 1}, live_context)
        questions = list_result.result.data["questions"]
        if not questions:
            pytest.skip("No questions in account to test with")

        question_id = questions[0]["id"]
        result = await fifteenfive.execute_action("get_question", {"question_id": question_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["question"]["id"] == question_id


# ---- Priorities & Pulses ----


class TestListPriorities:
    async def test_returns_priorities(self, live_context):
        result = await fifteenfive.execute_action("list_priorities", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "priorities" in result.result.data


class TestListPulses:
    async def test_returns_pulses(self, live_context):
        result = await fifteenfive.execute_action("list_pulses", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "pulses" in result.result.data


class TestGetPulse:
    async def test_fetches_a_real_pulse(self, live_context):
        list_result = await fifteenfive.execute_action("list_pulses", {"page": 1}, live_context)
        pulses = list_result.result.data["pulses"]
        if not pulses:
            pytest.skip("No pulse scores in account to test with")

        pulse_id = pulses[0]["id"]
        result = await fifteenfive.execute_action("get_pulse", {"pulse_id": pulse_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["pulse"]["id"] == pulse_id


# ---- Review Cycles ----


class TestListReviewCycles:
    async def test_returns_review_cycles(self, live_context):
        result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "review_cycles" in result.result.data


class TestGetReviewCycle:
    async def test_fetches_a_real_review_cycle(self, live_context):
        list_result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)
        review_cycles = list_result.result.data["review_cycles"]
        if not review_cycles:
            pytest.skip("No review cycles in account to test with")

        review_cycle_id = review_cycles[0]["id"]
        result = await fifteenfive.execute_action(
            "get_review_cycle", {"review_cycle_id": review_cycle_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["review_cycle"]["id"] == review_cycle_id


class TestListReviewCycleParticipants:
    async def test_returns_participants(self, live_context):
        list_result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)
        review_cycles = list_result.result.data["review_cycles"]
        if not review_cycles:
            pytest.skip("No review cycles in account to test with")

        review_cycle_id = review_cycles[0]["id"]
        result = await fifteenfive.execute_action(
            "list_review_cycle_participants", {"review_cycle_id": review_cycle_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert "participants" in result.result.data


class TestListReviewCycleResultsAnswers:
    async def test_returns_results(self, live_context):
        list_result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)
        review_cycles = list_result.result.data["review_cycles"]
        if not review_cycles:
            pytest.skip("No review cycles in account to test with")

        review_cycle_id = review_cycles[0]["id"]
        result = await fifteenfive.execute_action(
            "list_review_cycle_results_answers", {"review_cycle_id": review_cycle_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert "results" in result.result.data


class TestListReviewCycleResultsPerformanceMeasurements:
    async def test_returns_measurements(self, live_context):
        list_result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)
        review_cycles = list_result.result.data["review_cycles"]
        if not review_cycles:
            pytest.skip("No review cycles in account to test with")

        review_cycle_id = review_cycles[0]["id"]
        result = await fifteenfive.execute_action(
            "list_review_cycle_results_performance_measurements", {"review_cycle_id": review_cycle_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert "performance_measurements" in result.result.data


class TestListReviews:
    async def test_returns_reviews(self, live_context):
        list_result = await fifteenfive.execute_action("list_review_cycles", {"page": 1}, live_context)
        review_cycles = list_result.result.data["review_cycles"]
        if not review_cycles:
            pytest.skip("No review cycles in account to test with")

        review_cycle_id = review_cycles[0]["id"]
        result = await fifteenfive.execute_action("list_reviews", {"review_cycle_id": review_cycle_id}, live_context)

        assert result.type == ResultType.ACTION
        assert "reviews" in result.result.data


# ---- 1-on-1s ----


class TestListOneOnOnes:
    async def test_returns_one_on_ones(self, live_context):
        result = await fifteenfive.execute_action("list_one_on_ones", {"page": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "one_on_ones" in result.result.data


class TestGetOneOnOne:
    async def test_fetches_a_real_one_on_one(self, live_context):
        list_result = await fifteenfive.execute_action("list_one_on_ones", {"page": 1}, live_context)
        one_on_ones = list_result.result.data["one_on_ones"]
        if not one_on_ones:
            pytest.skip("No 1-on-1s in account to test with")

        one_on_one_id = one_on_ones[0]["id"]
        result = await fifteenfive.execute_action("get_one_on_one", {"one_on_one_id": one_on_one_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["one_on_one"]["id"] == one_on_one_id


# ---- Vacations & Security Audit ----


class TestListVacations:
    async def test_returns_vacations(self, live_context):
        result = await fifteenfive.execute_action("list_vacations", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "vacations" in result.result.data


class TestListSecurityAudit:
    async def test_returns_events(self, live_context):
        result = await fifteenfive.execute_action("list_security_audit", {}, live_context)

        assert result.type == ResultType.ACTION
        assert "events" in result.result.data


# ---- Destructive Tests (Write Operations) ----
# These create real, visible data in the connected 15Five account.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCreateHighFive:
    async def test_creates_high_five(self, live_context):
        require_creator_id()

        result = await fifteenfive.execute_action(
            "create_high_five",
            {"text": f"Integration test high five (pid {os.getpid()})", "creator_id": int(TEST_CREATOR_ID)},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["high_five"]["id"] is not None


@pytest.mark.destructive
class TestCreateAttribute:
    async def test_creates_attribute(self, live_context):
        result = await fifteenfive.execute_action(
            "create_attribute",
            {"name": f"Integration Test Attribute {os.getpid()}", "datatype": "text"},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert "attribute" in result.result.data


@pytest.mark.destructive
class TestCreateAttributeValue:
    async def test_creates_attribute_value(self, live_context):
        require_creator_id()

        attr_result = await fifteenfive.execute_action(
            "create_attribute",
            {"name": f"Integration Test Attribute Value {os.getpid()}", "datatype": "text"},
            live_context,
        )
        attribute_name = attr_result.result.data["attribute"]["name"]

        result = await fifteenfive.execute_action(
            "create_attribute_value",
            {"name": attribute_name, "value": "test-value", "user_id": int(TEST_CREATOR_ID)},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert "attribute_value" in result.result.data


@pytest.mark.destructive
class TestCreateObjectives:
    async def test_creates_objective(self, live_context):
        require_creator_id()

        result = await fifteenfive.execute_action(
            "create_objectives",
            {
                "objectives": [
                    {
                        "description": f"Integration test objective (pid {os.getpid()})",
                        "start_ts": "2026-01-01",
                        "end_ts": "2026-12-31",
                        "scope": "individual",
                        "user_id": int(TEST_CREATOR_ID),
                    }
                ]
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["objectives"]) == 1


@pytest.mark.destructive
class TestCreatePriorities:
    async def test_creates_priority(self, live_context):
        require_creator_id()

        result = await fifteenfive.execute_action(
            "create_priorities",
            {
                "priorities": [
                    {"user_id": int(TEST_CREATOR_ID), "text": f"Integration test priority (pid {os.getpid()})"}
                ]
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["priorities"]) == 1
