import pytest

from ci_readme_check import ci_readme_check

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_get_data(mock_context):
    result = await ci_readme_check.execute_action("get_data", {}, mock_context)

    assert result.result.data["message"] == "hello from ci_readme_check"
