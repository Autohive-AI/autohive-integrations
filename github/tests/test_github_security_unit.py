"""Unit tests for the GitHub security actions.

Covers code scanning, Dependabot, secret scanning, code quality and security
advisories. The secret scanning tests are the important ones: they assert that
the leaked credential never leaves the action, in either direction (request
sends ``hide_secret=true``, response is allow-listed).
"""

import json

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

OWNER = "octocat"
REPO = "Hello-World"
ORG = "octo-org"

SAMPLE_CODE_SCANNING_ALERT = {
    "number": 4,
    "state": "open",
    "created_at": "2020-02-13T12:29:18Z",
    "updated_at": "2020-02-14T12:29:18Z",
    "html_url": "https://github.com/octocat/Hello-World/security/code-scanning/4",
    "url": "https://api.github.com/repos/octocat/Hello-World/code-scanning/alerts/4",
    "fixed_at": None,
    "dismissed_at": None,
    "dismissed_reason": None,
    "dismissed_comment": None,
    "dismissed_by": None,
    "rule": {
        "id": "js/zipslip",
        "name": "js/zipslip",
        "description": "Arbitrary file write during zip extraction",
        "severity": "error",
        "security_severity_level": "high",
        "tags": ["security", "external/cwe/cwe-022"],
        "help_uri": "https://codeql.github.com/js/zipslip",
    },
    "tool": {"name": "CodeQL", "version": "2.4.0", "guid": None},
    "most_recent_instance": {
        "ref": "refs/heads/main",
        "commit_sha": "39406e42cb832f683daa691dd652a8dc36ee8930",
        "category": "/language:javascript",
        "state": "open",
        "message": {"text": "This path depends on a user-provided value."},
        "location": {"path": "lib/unzip.js", "start_line": 200, "end_line": 200},
    },
}

SAMPLE_DEPENDABOT_ALERT = {
    "number": 2,
    "state": "open",
    "created_at": "2022-06-14T15:21:52Z",
    "updated_at": "2022-06-15T15:21:52Z",
    "html_url": "https://github.com/octocat/Hello-World/security/dependabot/2",
    "fixed_at": None,
    "auto_dismissed_at": None,
    "dismissed_at": None,
    "dismissed_reason": None,
    "dismissed_comment": None,
    "dismissed_by": None,
    "dependency": {
        "package": {"ecosystem": "pip", "name": "django"},
        "manifest_path": "path/to/requirements.txt",
        "scope": "runtime",
    },
    "security_advisory": {
        "ghsa_id": "GHSA-rf4j-j272-fj86",
        "cve_id": "CVE-2018-6188",
        "summary": "Django allows remote attackers to obtain potentially sensitive information",
        "severity": "high",
    },
    "security_vulnerability": {
        "package": {"ecosystem": "pip", "name": "django"},
        "severity": "high",
        "vulnerable_version_range": ">= 2.0.0, < 2.0.2",
        "first_patched_version": {"identifier": "2.0.2"},
    },
}

# A fake credential literal, only used to prove it never reaches the output.
FAKE_LEAKED_SECRET = "ghp_0000000000000000000000000000000000AA"  # nosec B105

SAMPLE_SECRET_SCANNING_ALERT = {
    "number": 42,
    "state": "open",
    "resolution": None,
    "secret_type": "github_personal_access_token",  # nosec B105 - alert metadata, not a credential
    "secret_type_display_name": "GitHub Personal Access Token",  # nosec B105 - a label, not a credential
    "secret": FAKE_LEAKED_SECRET,
    "created_at": "2020-11-06T18:18:30Z",
    "updated_at": "2020-11-07T18:18:30Z",
    "html_url": "https://github.com/octocat/Hello-World/security/secret-scanning/42",
    "url": "https://api.github.com/repos/octocat/Hello-World/secret-scanning/alerts/42",
    "locations_url": "https://api.github.com/repos/octocat/Hello-World/secret-scanning/alerts/42/locations",
    "validity": "active",
    "push_protection_bypassed": False,
    "resolution_comment": f"Rotated {FAKE_LEAKED_SECRET}",
    "has_more_locations": True,
    "first_location_detected": {
        "type": "commit",
        "details": {
            "path": "/example/secrets.txt",
            "start_line": 1,
            "end_line": 1,
            "blob_sha": "af5626b4a114abcb82d63db7c8082c3c4756e51b",
        },
    },
    "is_base64_encoded": False,
}

SAMPLE_CODE_QUALITY_FINDING = {
    "number": 42,
    "state": "open",
    "url": "https://api.github.com/repos/octocat/Hello-World/code-quality/findings/42",
    "rule": {
        "id": "java/useless-null-check",
        "title": "Useless null check",
        "description": "Checking whether an expression is null when it cannot be null is useless.",
        "severity": "warning",
        "category": "maintainability",
    },
    "location": {
        "path": "java/UselessNullCheck.java",
        "start_line": 9,
        "start_column": 4,
        "end_line": 9,
        "end_column": 18,
    },
    "message": {"text": "This check is useless.", "markdown": "This check is *useless*."},
    "created_at": "2026-01-23T12:34:56Z",
}

SAMPLE_GLOBAL_ADVISORY = {
    "ghsa_id": "GHSA-abcd-1234-efgh",
    "cve_id": "CVE-2050-00000",
    "summary": "A vulnerability in a-package",
    "description": "A longer description of the vulnerability.",
    "type": "reviewed",
    "severity": "critical",
    "html_url": "https://github.com/advisories/GHSA-abcd-1234-efgh",
    "url": "https://api.github.com/advisories/GHSA-abcd-1234-efgh",
    "source_code_location": "https://github.com/project/a-package",
    "repository_advisory_url": None,
    "published_at": "2050-01-03T00:00:00Z",
    "updated_at": "2050-01-04T00:00:00Z",
    "github_reviewed_at": "2050-01-03T00:00:00Z",
    "nvd_published_at": None,
    "withdrawn_at": None,
    "identifiers": [
        {"type": "GHSA", "value": "GHSA-abcd-1234-efgh"},
        {"type": "CVE", "value": "CVE-2050-00000"},
    ],
    "references": ["https://github.com/advisories/GHSA-abcd-1234-efgh"],
    "cwes": [{"cwe_id": "CWE-123", "name": "A CWE"}],
    "cvss": {"vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "score": 9.8},
    "vulnerabilities": [
        {
            "package": {"ecosystem": "pip", "name": "a-package"},
            "vulnerable_version_range": ">= 1.0.0, < 1.0.1",
            "first_patched_version": "1.0.1",
        }
    ],
}

SAMPLE_REPOSITORY_ADVISORY = {
    "ghsa_id": "GHSA-abcd-1234-efgh",
    "cve_id": None,
    "summary": "A draft advisory",
    "description": "Details still under embargo.",
    "severity": "high",
    "state": "draft",
    "html_url": "https://github.com/octocat/Hello-World/security/advisories/GHSA-abcd-1234-efgh",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2020-01-02T00:00:00Z",
    "published_at": None,
    "closed_at": None,
    "withdrawn_at": None,
    "author": {"login": "octocat", "avatar_url": "https://github.com/images/octocat.gif"},
    "publisher": None,
    "identifiers": [{"type": "GHSA", "value": "GHSA-abcd-1234-efgh"}],
    "cwe_ids": ["CWE-123"],
    "cvss": {"vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "score": 8.8},
    "vulnerabilities": [
        {
            "package": {"ecosystem": "pip", "name": "a-package"},
            "vulnerable_version_range": ">= 1.0.0, < 1.0.1",
            "patched_versions": "1.0.1",
            "vulnerable_functions": ["function1"],
        }
    ],
}


def _response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def _requested_url(mock_context):
    return mock_context.fetch.call_args.args[0]


def _requested_params(mock_context):
    return mock_context.fetch.call_args.kwargs.get("params") or {}


class TestListCodeScanningAlerts:
    @pytest.mark.asyncio
    async def test_returns_shaped_alerts(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_CODE_SCANNING_ALERT])

        result = await github.execute_action("list_code_scanning_alerts", {"owner": OWNER, "repo": REPO}, mock_context)

        alert = result.result.data[0]
        assert alert["number"] == 4
        assert alert["severity"] == "high"
        assert alert["url"] == SAMPLE_CODE_SCANNING_ALERT["html_url"]
        assert alert["rule"]["id"] == "js/zipslip"
        assert alert["tool"]["name"] == "CodeQL"
        assert alert["most_recent_instance"]["path"] == "lib/unzip.js"
        assert alert["most_recent_instance"]["message"] == "This path depends on a user-provided value."

    @pytest.mark.asyncio
    async def test_repository_scope_sends_filters(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_code_scanning_alerts",
            {"owner": OWNER, "repo": REPO, "state": "open", "severity": "high", "tool_name": "CodeQL", "ref": "main"},
            mock_context,
        )

        assert _requested_url(mock_context) == "https://api.github.com/repos/octocat/Hello-World/code-scanning/alerts"
        params = _requested_params(mock_context)
        assert params["state"] == "open"
        assert params["severity"] == "high"
        assert params["tool_name"] == "CodeQL"
        assert params["ref"] == "main"

    @pytest.mark.asyncio
    async def test_org_scope_uses_org_url_and_drops_repo_only_filters(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action("list_code_scanning_alerts", {"org": ORG, "ref": "main", "pr": 7}, mock_context)

        assert _requested_url(mock_context) == "https://api.github.com/orgs/octo-org/code-scanning/alerts"
        params = _requested_params(mock_context)
        assert "ref" not in params
        assert "pr" not in params

    @pytest.mark.asyncio
    async def test_missing_scope_returns_action_error(self, mock_context):
        result = await github.execute_action("list_code_scanning_alerts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "org" in result.result.message
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        first_page = [dict(SAMPLE_CODE_SCANNING_ALERT, number=n) for n in range(100)]
        second_page = [dict(SAMPLE_CODE_SCANNING_ALERT, number=100)]
        mock_context.fetch.side_effect = [_response(first_page), _response(second_page)]

        result = await github.execute_action(
            "list_code_scanning_alerts", {"owner": OWNER, "repo": REPO, "limit": 500}, mock_context
        )

        assert mock_context.fetch.await_count == 2
        assert len(result.result.data) == 101

    @pytest.mark.asyncio
    async def test_limit_is_clamped_to_one_page_worth(self, mock_context):
        mock_context.fetch.return_value = _response([dict(SAMPLE_CODE_SCANNING_ALERT, number=n) for n in range(100)])

        result = await github.execute_action(
            "list_code_scanning_alerts", {"owner": OWNER, "repo": REPO, "limit": 25}, mock_context
        )

        assert _requested_params(mock_context)["per_page"] == 25
        assert len(result.result.data) == 25

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("list_code_scanning_alerts", {"owner": OWNER, "repo": REPO}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


class TestGetCodeScanningAlert:
    @pytest.mark.asyncio
    async def test_returns_alert(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_CODE_SCANNING_ALERT)

        result = await github.execute_action(
            "get_code_scanning_alert", {"owner": OWNER, "repo": REPO, "alert_number": 4}, mock_context
        )

        assert result.result.data["number"] == 4
        assert _requested_url(mock_context).endswith("/repos/octocat/Hello-World/code-scanning/alerts/4")

    @pytest.mark.asyncio
    async def test_forbidden_response_surfaces_as_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 403: Advanced Security must be enabled for this repository")

        result = await github.execute_action(
            "get_code_scanning_alert", {"owner": OWNER, "repo": REPO, "alert_number": 4}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "403" in result.result.message


class TestListDependabotAlerts:
    @pytest.mark.asyncio
    async def test_returns_shaped_alerts(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_DEPENDABOT_ALERT])

        result = await github.execute_action("list_dependabot_alerts", {"owner": OWNER, "repo": REPO}, mock_context)

        alert = result.result.data[0]
        assert alert["number"] == 2
        assert alert["package"] == "django"
        assert alert["ecosystem"] == "pip"
        assert alert["severity"] == "high"
        assert alert["first_patched_version"] == "2.0.2"
        assert alert["ghsa_id"] == "GHSA-rf4j-j272-fj86"

    @pytest.mark.asyncio
    async def test_sends_documented_filters(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_dependabot_alerts",
            {
                "owner": OWNER,
                "repo": REPO,
                "state": "open",
                "severity": "critical",
                "ecosystem": "pip",
                "package": "django",
                "scope": "runtime",
            },
            mock_context,
        )

        params = _requested_params(mock_context)
        assert params["state"] == "open"
        assert params["severity"] == "critical"
        assert params["ecosystem"] == "pip"
        assert params["package"] == "django"
        assert params["scope"] == "runtime"

    @pytest.mark.asyncio
    async def test_org_scope_uses_org_url(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action("list_dependabot_alerts", {"org": ORG}, mock_context)

        assert _requested_url(mock_context) == "https://api.github.com/orgs/octo-org/dependabot/alerts"

    @pytest.mark.asyncio
    async def test_cursor_endpoint_makes_a_single_request(self, mock_context):
        """This endpoint ignores ?page, so a full page must not trigger a second fetch."""
        mock_context.fetch.return_value = _response([dict(SAMPLE_DEPENDABOT_ALERT, number=n) for n in range(100)])

        result = await github.execute_action(
            "list_dependabot_alerts", {"owner": OWNER, "repo": REPO, "limit": 500}, mock_context
        )

        assert mock_context.fetch.await_count == 1
        assert len(result.result.data) == 100


class TestGetDependabotAlert:
    @pytest.mark.asyncio
    async def test_returns_alert(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_DEPENDABOT_ALERT)

        result = await github.execute_action(
            "get_dependabot_alert", {"owner": OWNER, "repo": REPO, "alert_number": 2}, mock_context
        )

        assert result.result.data["vulnerable_version_range"] == ">= 2.0.0, < 2.0.2"
        assert _requested_url(mock_context).endswith("/repos/octocat/Hello-World/dependabot/alerts/2")


class TestListSecretScanningAlerts:
    @pytest.mark.asyncio
    async def test_returns_shaped_alerts(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_SECRET_SCANNING_ALERT])

        result = await github.execute_action(
            "list_secret_scanning_alerts", {"owner": OWNER, "repo": REPO}, mock_context
        )

        alert = result.result.data[0]
        assert alert["number"] == 42
        assert alert["secret_type"] == "github_personal_access_token"
        assert alert["validity"] == "active"
        assert alert["has_more_locations"] is True
        assert alert["first_location"]["path"] == "/example/secrets.txt"

    @pytest.mark.asyncio
    async def test_never_returns_the_leaked_secret(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_SECRET_SCANNING_ALERT])

        result = await github.execute_action(
            "list_secret_scanning_alerts", {"owner": OWNER, "repo": REPO}, mock_context
        )

        serialised = json.dumps(result.result.data)
        assert "ghp_" not in serialised
        assert FAKE_LEAKED_SECRET not in serialised
        assert "secret" not in result.result.data[0]
        assert "resolution_comment" not in result.result.data[0]

    @pytest.mark.asyncio
    async def test_always_requests_hide_secret(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action("list_secret_scanning_alerts", {"owner": OWNER, "repo": REPO}, mock_context)

        assert _requested_params(mock_context)["hide_secret"] == "true"

    @pytest.mark.asyncio
    async def test_hide_secret_cannot_be_disabled_by_input(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_secret_scanning_alerts",
            {"owner": OWNER, "repo": REPO, "hide_secret": False},  # nosec B105 - a flag, not a credential
            mock_context,
        )

        assert _requested_params(mock_context)["hide_secret"] == "true"

    @pytest.mark.asyncio
    async def test_org_scope_uses_org_url(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action("list_secret_scanning_alerts", {"org": ORG}, mock_context)

        assert _requested_url(mock_context) == "https://api.github.com/orgs/octo-org/secret-scanning/alerts"


class TestGetSecretScanningAlert:
    @pytest.mark.asyncio
    async def test_returns_alert_metadata(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_SECRET_SCANNING_ALERT)

        result = await github.execute_action(
            "get_secret_scanning_alert", {"owner": OWNER, "repo": REPO, "alert_number": 42}, mock_context
        )

        assert result.result.data["secret_type_display_name"] == "GitHub Personal Access Token"
        assert _requested_url(mock_context).endswith("/repos/octocat/Hello-World/secret-scanning/alerts/42")

    @pytest.mark.asyncio
    async def test_never_returns_the_leaked_secret(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_SECRET_SCANNING_ALERT)

        result = await github.execute_action(
            "get_secret_scanning_alert", {"owner": OWNER, "repo": REPO, "alert_number": 42}, mock_context
        )

        serialised = json.dumps(result.result.data)
        assert "ghp_" not in serialised
        assert FAKE_LEAKED_SECRET not in serialised
        assert "secret" not in result.result.data

    @pytest.mark.asyncio
    async def test_always_requests_hide_secret(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_SECRET_SCANNING_ALERT)

        await github.execute_action(
            "get_secret_scanning_alert", {"owner": OWNER, "repo": REPO, "alert_number": 42}, mock_context
        )

        assert _requested_params(mock_context)["hide_secret"] == "true"


class TestListCodeQualityFindings:
    @pytest.mark.asyncio
    async def test_returns_shaped_findings(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_CODE_QUALITY_FINDING])

        result = await github.execute_action("list_code_quality_findings", {"owner": OWNER, "repo": REPO}, mock_context)

        finding = result.result.data[0]
        assert finding["number"] == 42
        assert finding["severity"] == "warning"
        assert finding["message"] == "This check is useless."
        assert finding["rule"]["category"] == "maintainability"
        assert finding["location"]["path"] == "java/UselessNullCheck.java"

    @pytest.mark.asyncio
    async def test_sends_state_filter_to_repo_endpoint(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_code_quality_findings", {"owner": OWNER, "repo": REPO, "state": "open"}, mock_context
        )

        assert _requested_url(mock_context) == "https://api.github.com/repos/octocat/Hello-World/code-quality/findings"
        assert _requested_params(mock_context)["state"] == "open"

    @pytest.mark.asyncio
    async def test_cursor_endpoint_makes_a_single_request(self, mock_context):
        mock_context.fetch.return_value = _response([dict(SAMPLE_CODE_QUALITY_FINDING, number=n) for n in range(100)])

        result = await github.execute_action(
            "list_code_quality_findings", {"owner": OWNER, "repo": REPO, "limit": 500}, mock_context
        )

        assert mock_context.fetch.await_count == 1
        assert len(result.result.data) == 100


class TestGetCodeQualityFinding:
    @pytest.mark.asyncio
    async def test_returns_finding(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_CODE_QUALITY_FINDING)

        result = await github.execute_action(
            "get_code_quality_finding", {"owner": OWNER, "repo": REPO, "finding_number": 42}, mock_context
        )

        assert result.result.data["rule"]["id"] == "java/useless-null-check"
        assert _requested_url(mock_context).endswith("/repos/octocat/Hello-World/code-quality/findings/42")


class TestListGlobalSecurityAdvisories:
    @pytest.mark.asyncio
    async def test_returns_shaped_advisories(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_GLOBAL_ADVISORY])

        result = await github.execute_action("list_global_security_advisories", {}, mock_context)

        advisory = result.result.data[0]
        assert advisory["ghsa_id"] == "GHSA-abcd-1234-efgh"
        assert advisory["url"] == SAMPLE_GLOBAL_ADVISORY["html_url"]
        assert advisory["cvss"]["score"] == 9.8
        assert advisory["vulnerabilities"][0]["package"] == "a-package"
        assert advisory["vulnerabilities"][0]["first_patched_version"] == "1.0.1"

    @pytest.mark.asyncio
    async def test_sends_search_filters(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_global_security_advisories",
            {"ecosystem": "npm", "severity": "critical", "type": "reviewed", "is_withdrawn": False},
            mock_context,
        )

        assert _requested_url(mock_context) == "https://api.github.com/advisories"
        params = _requested_params(mock_context)
        assert params["ecosystem"] == "npm"
        assert params["severity"] == "critical"
        assert params["type"] == "reviewed"
        assert params["is_withdrawn"] == "false"

    @pytest.mark.asyncio
    async def test_cursor_endpoint_makes_a_single_request(self, mock_context):
        mock_context.fetch.return_value = _response([dict(SAMPLE_GLOBAL_ADVISORY) for _ in range(100)])

        result = await github.execute_action("list_global_security_advisories", {"limit": 500}, mock_context)

        assert mock_context.fetch.await_count == 1
        assert len(result.result.data) == 100


class TestGetGlobalSecurityAdvisory:
    @pytest.mark.asyncio
    async def test_returns_advisory(self, mock_context):
        mock_context.fetch.return_value = _response(SAMPLE_GLOBAL_ADVISORY)

        result = await github.execute_action(
            "get_global_security_advisory", {"ghsa_id": "GHSA-abcd-1234-efgh"}, mock_context
        )

        assert result.result.data["cve_id"] == "CVE-2050-00000"
        assert _requested_url(mock_context).endswith("/advisories/GHSA-abcd-1234-efgh")


class TestListRepositorySecurityAdvisories:
    @pytest.mark.asyncio
    async def test_returns_shaped_advisories(self, mock_context):
        mock_context.fetch.return_value = _response([SAMPLE_REPOSITORY_ADVISORY])

        result = await github.execute_action(
            "list_repository_security_advisories", {"owner": OWNER, "repo": REPO}, mock_context
        )

        advisory = result.result.data[0]
        assert advisory["state"] == "draft"
        assert advisory["author"] == {
            "login": "octocat",
            "avatar_url": "https://github.com/images/octocat.gif",
        }
        assert advisory["publisher"] is None
        assert advisory["vulnerabilities"][0]["patched_versions"] == "1.0.1"

    @pytest.mark.asyncio
    async def test_repository_scope_uses_repo_url(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action(
            "list_repository_security_advisories", {"owner": OWNER, "repo": REPO, "state": "triage"}, mock_context
        )

        assert _requested_url(mock_context) == "https://api.github.com/repos/octocat/Hello-World/security-advisories"
        assert _requested_params(mock_context)["state"] == "triage"

    @pytest.mark.asyncio
    async def test_org_scope_uses_org_url(self, mock_context):
        mock_context.fetch.return_value = _response([])

        await github.execute_action("list_repository_security_advisories", {"org": ORG}, mock_context)

        assert _requested_url(mock_context) == "https://api.github.com/orgs/octo-org/security-advisories"

    @pytest.mark.asyncio
    async def test_missing_scope_returns_action_error(self, mock_context):
        result = await github.execute_action("list_repository_security_advisories", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()
