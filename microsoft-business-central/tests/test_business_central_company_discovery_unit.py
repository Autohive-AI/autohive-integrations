"""Verify live-test company discovery without credentials or API calls."""

import pytest
from autohive_integrations_sdk import FetchResponse

from businesscentral import base_url
from .test_business_central_integration import live_inputs

pytestmark = pytest.mark.unit
ENV = {
    "MICROSOFT_BUSINESS_CENTRAL_TENANT_ID": "11111111-1111-1111-1111-111111111111",
    "MICROSOFT_BUSINESS_CENTRAL_ENVIRONMENT": "Production",
}
COMPANY = "22222222-2222-2222-2222-222222222222"
OTHER = "33333333-3333-3333-3333-333333333333"
INPUTS = {"tenant_id": ENV["MICROSOFT_BUSINESS_CENTRAL_TENANT_ID"], "environment": "Production"}
LINK = base_url(INPUTS, company=False) + "/companies?$skiptoken=next"


def response(records, next_link=None):
    data = {"value": records}
    if next_link:
        data["@odata.nextLink"] = next_link
    return FetchResponse(status=200, headers={}, data=data)


async def test_discovers_exact_demo_company_instead_of_first_company(mock_context):
    mock_context.request.return_value = response(
        [
            {"id": OTHER, "name": "Other Company"},
            {"id": COMPANY, "name": "CRONUS NZ"},
        ]
    )
    inputs = await live_inputs.__wrapped__(ENV.get, mock_context)
    assert inputs == dict(INPUTS, company_id=COMPANY)
    assert mock_context.request.await_args.args == (base_url(INPUTS, company=False) + "/companies",)
    assert mock_context.request.await_args.kwargs["method"] == "GET"


async def test_exact_company_name_is_configurable(mock_context):
    mock_context.request.return_value = response(
        [
            {"id": OTHER, "name": "CRONUS NZ"},
            {"id": COMPANY, "name": "CRONUS NZ Ltd."},
        ]
    )
    env = ENV | {"MICROSOFT_BUSINESS_CENTRAL_COMPANY_NAME": "CRONUS NZ Ltd."}
    assert (await live_inputs.__wrapped__(env.get, mock_context))["company_id"] == COMPANY


async def test_discovers_match_on_later_page(mock_context):
    mock_context.request.side_effect = [
        response([{"id": OTHER, "name": "Other Company"}], LINK),
        response([{"id": COMPANY, "name": "CRONUS NZ"}]),
    ]
    assert (await live_inputs.__wrapped__(ENV.get, mock_context))["company_id"] == COMPANY
    assert mock_context.request.await_args.args == (LINK,)


async def test_checks_later_pages_for_ambiguous_matches(mock_context):
    mock_context.request.side_effect = [
        response([{"id": COMPANY, "name": "CRONUS NZ"}], LINK),
        response([{"id": OTHER, "name": "CRONUS NZ"}]),
    ]
    with pytest.raises(pytest.fail.Exception, match="found 2 matches"):
        await live_inputs.__wrapped__(ENV.get, mock_context)


@pytest.mark.parametrize("records", [[], [{"id": COMPANY, "name": "Other Company"}], [{"name": "CRONUS NZ"}]])
async def test_missing_company_or_id_fails_instead_of_selecting_a_fallback(mock_context, records):
    mock_context.request.return_value = response(records)
    with pytest.raises(pytest.fail.Exception, match="Expected exactly one company"):
        await live_inputs.__wrapped__(ENV.get, mock_context)


async def test_repeated_continuation_fails_without_selecting_a_company(mock_context):
    mock_context.request.return_value = response([], LINK)
    with pytest.raises(pytest.fail.Exception, match="repeated continuation"):
        await live_inputs.__wrapped__(ENV.get, mock_context)
    assert mock_context.request.await_count == 2


async def test_discovery_failure_is_not_treated_as_a_missing_company(mock_context):
    mock_context.request.return_value = FetchResponse(status=403, headers={}, data=None)
    with pytest.raises(AssertionError, match="list_companies failed"):
        await live_inputs.__wrapped__(ENV.get, mock_context)


@pytest.mark.parametrize("missing", list(ENV))
async def test_missing_tenant_or_environment_skips_without_api_calls(mock_context, missing):
    env = {key: value for key, value in ENV.items() if key != missing}
    with pytest.raises(pytest.skip.Exception):
        await live_inputs.__wrapped__(env.get, mock_context)
    mock_context.request.assert_not_awaited()
