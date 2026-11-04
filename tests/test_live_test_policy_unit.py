"""Exercise live-test reporting in a separate pytest run, including JUnit output."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

pytest_plugins = ["pytester"]
pytestmark = pytest.mark.unit


def test_read_only_skips_fail_and_preserve_the_reason(pytester):
    pytester.makeconftest((Path(__file__).resolve().parents[1] / "conftest.py").read_text())
    pytester.makepyfile("""
        import pytest

        @pytest.fixture
        def missing_resource():
            pytest.skip("TEST_FORM_ID is missing")

        @pytest.mark.integration
        def test_missing_resource(missing_resource):
            pass

        @pytest.mark.integration
        @pytest.mark.skipif(True, reason="No verified site")
        def test_skip_marker():
            pass

        @pytest.mark.integration
        def test_empty_results():
            pytest.skip("No publications returned")

        @pytest.mark.integration
        def test_success():
            assert True

        @pytest.mark.unit
        def test_optional_unit():
            pytest.skip("Unit-only skip")

        @pytest.mark.integration
        @pytest.mark.destructive
        def test_write():
            raise AssertionError("Write tests must not run")
    """)
    result = pytester.runpytest_subprocess("-m", "not destructive", "--junitxml=results.xml")
    result.assert_outcomes(passed=1, failed=1, errors=2, skipped=1, deselected=1)
    root = ElementTree.parse(pytester.path / "results.xml")
    cases = {case.get("name"): case for case in root.iter("testcase")}
    for name, reason in (
        ("test_missing_resource", "TEST_FORM_ID is missing"),
        ("test_skip_marker", "No verified site"),
        ("test_empty_results", "No publications returned"),
    ):
        case = cases[name]
        assert case.find("skipped") is None
        assert "Read-only live test did not run" in ElementTree.tostring(case, encoding="unicode")
        assert reason in ElementTree.tostring(case, encoding="unicode")
    assert cases["test_optional_unit"].find("skipped") is not None
