"""
GitHub integration - Security actions - code scanning, Dependabot, secret scanning, code quality, and advisories.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional

from github import github
from helpers import GitHubAPI, handle_github_errors

# ---------------------------------------------------------------------------
# Pagination policy
# ---------------------------------------------------------------------------
# Only the code scanning and secret scanning alert endpoints document a ``page``
# query parameter. Dependabot alerts, code quality findings and both security
# advisory endpoints are cursor-paginated (``before``/``after`` taken from the
# Link header) and silently ignore ``page`` -- verified against GET /advisories,
# where ``page=1`` and ``page=2`` return an identical result set. Walking those
# with ``paginated_fetch`` would hand back the first page over and over, so they
# are capped at a single request: ``limit`` <= ``per_page`` makes
# ``paginated_fetch`` return before it ever asks for a second page.
CURSOR_PAGE_MAX = 100
PAGED_MAX_RESULTS = 1000
PAGED_MAX_PAGES = 10
DEFAULT_LIMIT = 100

_SCOPE_REQUIRED = (
    "Specify the target: pass 'owner' and 'repo' for a single repository, or 'org' for an organization-wide query."
)


def _resolve_limit(raw: Any, maximum: int) -> int:
    """Clamp the caller's ``limit`` into ``1..maximum``, falling back to the default."""
    try:
        value = int(raw) if raw is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, maximum))


def _scoped_url(owner: Optional[str], repo: Optional[str], org: Optional[str], suffix: str) -> str:
    """Build a repository- or organization-scoped URL for an endpoint offered at both levels.

    ``owner`` + ``repo`` wins over ``org`` when both are supplied. Raises when neither
    identifies a target, so the error decorator surfaces an actionable message instead of
    a 404 from a malformed URL.
    """
    if owner and repo:
        return f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/{suffix}"
    if org:
        return f"{GitHubAPI.BASE_URL}/orgs/{org}/{suffix}"
    raise ValueError(_SCOPE_REQUIRED)


def _compact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop unset filters and render booleans the way GitHub expects.

    The SDK stringifies query values with ``str()``, which would turn ``True`` into
    ``"True"``; GitHub wants lowercase ``true``/``false``.
    """
    compacted: Dict[str, Any] = {}
    for name, value in params.items():
        if value is None or value == "":
            continue
        if value is True:
            compacted[name] = "true"
        elif value is False:
            compacted[name] = "false"
        else:
            compacted[name] = value
    return compacted


async def _get_json(context: ExecutionContext, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET a single JSON resource from the GitHub REST API."""
    return (await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))).data


def _shape_user(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Flatten a GitHub user object, tolerating the nulls GitHub returns for deleted accounts."""
    if not user:
        return None
    return {"login": user.get("login"), "avatar_url": user.get("avatar_url")}


def _repository_full_name(payload: Dict[str, Any]) -> Optional[str]:
    """Pull ``full_name`` from the repository GitHub attaches to organization-level results."""
    repository = payload.get("repository") or {}
    return repository.get("full_name")


def _shape_identifiers(advisory: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Shape the GHSA/CVE identifier pairs attached to an advisory."""
    return [
        {"type": identifier.get("type"), "value": identifier.get("value")}
        for identifier in advisory.get("identifiers") or []
    ]


def _shape_cwes(advisory: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Shape the CWE list attached to an advisory."""
    return [{"cwe_id": cwe.get("cwe_id"), "name": cwe.get("name")} for cwe in advisory.get("cwes") or []]


def _shape_cvss(advisory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Shape the top-level CVSS block of an advisory."""
    cvss = advisory.get("cvss") or {}
    if not cvss:
        return None
    return {"score": cvss.get("score"), "vector_string": cvss.get("vector_string")}


# ---------------------------------------------------------------------------
# Response shaping
# ---------------------------------------------------------------------------


def _shape_code_scanning_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a code scanning alert: the shared alert envelope plus static-analysis detail."""
    rule = alert.get("rule") or {}
    tool = alert.get("tool") or {}
    instance = alert.get("most_recent_instance") or {}
    location = instance.get("location") or {}
    message = instance.get("message") or {}

    return {
        "number": alert.get("number"),
        "state": alert.get("state"),
        "severity": rule.get("security_severity_level") or rule.get("severity"),
        "created_at": alert.get("created_at"),
        "updated_at": alert.get("updated_at"),
        "url": alert.get("html_url"),
        "fixed_at": alert.get("fixed_at"),
        "dismissed_at": alert.get("dismissed_at"),
        "dismissed_reason": alert.get("dismissed_reason"),
        "dismissed_comment": alert.get("dismissed_comment"),
        "dismissed_by": _shape_user(alert.get("dismissed_by")),
        "rule": {
            "id": rule.get("id"),
            "name": rule.get("name"),
            "description": rule.get("description"),
            "severity": rule.get("severity"),
            "security_severity_level": rule.get("security_severity_level"),
            "tags": rule.get("tags") or [],
            "help_uri": rule.get("help_uri"),
        }
        if rule
        else None,
        "tool": {"name": tool.get("name"), "version": tool.get("version"), "guid": tool.get("guid")} if tool else None,
        "most_recent_instance": {
            "ref": instance.get("ref"),
            "commit_sha": instance.get("commit_sha"),
            "category": instance.get("category"),
            "state": instance.get("state"),
            "message": message.get("text"),
            "path": location.get("path"),
            "start_line": location.get("start_line"),
            "end_line": location.get("end_line"),
        }
        if instance
        else None,
        "repository": _repository_full_name(alert),
    }


def _shape_dependabot_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a Dependabot alert: the shared alert envelope plus vulnerable-dependency detail."""
    dependency = alert.get("dependency") or {}
    package = dependency.get("package") or {}
    advisory = alert.get("security_advisory") or {}
    vulnerability = alert.get("security_vulnerability") or {}

    return {
        "number": alert.get("number"),
        "state": alert.get("state"),
        "severity": advisory.get("severity") or vulnerability.get("severity"),
        "created_at": alert.get("created_at"),
        "updated_at": alert.get("updated_at"),
        "url": alert.get("html_url"),
        "fixed_at": alert.get("fixed_at"),
        "auto_dismissed_at": alert.get("auto_dismissed_at"),
        "dismissed_at": alert.get("dismissed_at"),
        "dismissed_reason": alert.get("dismissed_reason"),
        "dismissed_comment": alert.get("dismissed_comment"),
        "dismissed_by": _shape_user(alert.get("dismissed_by")),
        "package": package.get("name"),
        "ecosystem": package.get("ecosystem"),
        "manifest_path": dependency.get("manifest_path"),
        "scope": dependency.get("scope"),
        "ghsa_id": advisory.get("ghsa_id"),
        "cve_id": advisory.get("cve_id"),
        "summary": advisory.get("summary"),
        "vulnerable_version_range": vulnerability.get("vulnerable_version_range"),
        "first_patched_version": (vulnerability.get("first_patched_version") or {}).get("identifier"),
        "repository": _repository_full_name(alert),
    }


def _shape_secret_scanning_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a secret scanning alert, deliberately dropping the leaked credential.

    GitHub returns the literal leaked value in ``secret`` and can echo it back inside
    ``resolution_comment`` or ``metadata``. Every caller here also sends
    ``hide_secret=true``, but this allow-list is the belt-and-braces guarantee: only the
    fields named below ever leave the action, so a GitHub-side regression -- or a stored
    payload captured before ``hide_secret`` existed -- still cannot leak the credential
    into a workflow, a log line, or a downstream step.
    """
    location = alert.get("first_location_detected") or {}
    details = location.get("details") or {}

    return {
        "number": alert.get("number"),
        "state": alert.get("state"),
        "resolution": alert.get("resolution"),
        "secret_type": alert.get("secret_type"),
        "secret_type_display_name": alert.get("secret_type_display_name"),
        "created_at": alert.get("created_at"),
        "updated_at": alert.get("updated_at"),
        "url": alert.get("html_url"),
        "validity": alert.get("validity"),
        "push_protection_bypassed": alert.get("push_protection_bypassed"),
        "has_more_locations": alert.get("has_more_locations"),
        "first_location": {
            "type": location.get("type"),
            "path": details.get("path"),
            "start_line": details.get("start_line"),
            "end_line": details.get("end_line"),
        }
        if location
        else None,
        "repository": _repository_full_name(alert),
    }


def _shape_code_quality_finding(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a code quality finding: the shared envelope plus rule and source location."""
    rule = finding.get("rule") or {}
    location = finding.get("location") or {}
    message = finding.get("message") or {}

    return {
        "number": finding.get("number"),
        "state": finding.get("state"),
        "severity": rule.get("severity"),
        "created_at": finding.get("created_at"),
        "url": finding.get("url"),
        "message": message.get("text"),
        "rule": {
            "id": rule.get("id"),
            "title": rule.get("title"),
            "description": rule.get("description"),
            "category": rule.get("category"),
            "severity": rule.get("severity"),
            "help": rule.get("help"),
        }
        if rule
        else None,
        "location": {
            "path": location.get("path"),
            "start_line": location.get("start_line"),
            "start_column": location.get("start_column"),
            "end_line": location.get("end_line"),
            "end_column": location.get("end_column"),
        }
        if location
        else None,
    }


def _shape_global_advisory(advisory: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a global (GitHub Advisory Database) security advisory."""
    return {
        "ghsa_id": advisory.get("ghsa_id"),
        "cve_id": advisory.get("cve_id"),
        "summary": advisory.get("summary"),
        "description": advisory.get("description"),
        "type": advisory.get("type"),
        "severity": advisory.get("severity"),
        "url": advisory.get("html_url"),
        "source_code_location": advisory.get("source_code_location"),
        "repository_advisory_url": advisory.get("repository_advisory_url"),
        "published_at": advisory.get("published_at"),
        "updated_at": advisory.get("updated_at"),
        "github_reviewed_at": advisory.get("github_reviewed_at"),
        "nvd_published_at": advisory.get("nvd_published_at"),
        "withdrawn_at": advisory.get("withdrawn_at"),
        "identifiers": _shape_identifiers(advisory),
        "references": advisory.get("references") or [],
        "cwes": _shape_cwes(advisory),
        "cvss": _shape_cvss(advisory),
        "vulnerabilities": [
            {
                "package": (vulnerability.get("package") or {}).get("name"),
                "ecosystem": (vulnerability.get("package") or {}).get("ecosystem"),
                "vulnerable_version_range": vulnerability.get("vulnerable_version_range"),
                "first_patched_version": vulnerability.get("first_patched_version"),
            }
            for vulnerability in advisory.get("vulnerabilities") or []
        ],
    }


def _shape_repository_advisory(advisory: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a repository security advisory (draft, triage, published, or closed)."""
    return {
        "ghsa_id": advisory.get("ghsa_id"),
        "cve_id": advisory.get("cve_id"),
        "summary": advisory.get("summary"),
        "description": advisory.get("description"),
        "severity": advisory.get("severity"),
        "state": advisory.get("state"),
        "url": advisory.get("html_url"),
        "created_at": advisory.get("created_at"),
        "updated_at": advisory.get("updated_at"),
        "published_at": advisory.get("published_at"),
        "closed_at": advisory.get("closed_at"),
        "withdrawn_at": advisory.get("withdrawn_at"),
        "author": _shape_user(advisory.get("author")),
        "publisher": _shape_user(advisory.get("publisher")),
        "identifiers": _shape_identifiers(advisory),
        "cwe_ids": advisory.get("cwe_ids") or [],
        "cvss": _shape_cvss(advisory),
        "vulnerabilities": [
            {
                "package": (vulnerability.get("package") or {}).get("name"),
                "ecosystem": (vulnerability.get("package") or {}).get("ecosystem"),
                "vulnerable_version_range": vulnerability.get("vulnerable_version_range"),
                "patched_versions": vulnerability.get("patched_versions"),
            }
            for vulnerability in advisory.get("vulnerabilities") or []
        ],
    }


# ---------------------------------------------------------------------------
# Code scanning
# ---------------------------------------------------------------------------


@github.action("list_code_scanning_alerts")
class ListCodeScanningAlerts(ActionHandler):
    """List code scanning alerts for a repository or an organization"""

    @handle_github_errors("list_code_scanning_alerts")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        owner = inputs.get("owner")
        repo = inputs.get("repo")
        url = _scoped_url(owner, repo, inputs.get("org"), "code-scanning/alerts")

        params = _compact(
            {
                "state": inputs.get("state"),
                "severity": inputs.get("severity"),
                "tool_name": inputs.get("tool_name"),
                "sort": inputs.get("sort"),
                "direction": inputs.get("direction"),
                # ref and pr only exist on the repository-level endpoint.
                "ref": inputs.get("ref") if owner and repo else None,
                "pr": inputs.get("pr") if owner and repo else None,
            }
        )

        alerts = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), PAGED_MAX_RESULTS),
            max_pages=PAGED_MAX_PAGES,
        )

        return ActionResult(
            data=[_shape_code_scanning_alert(alert) for alert in alerts],
            cost_usd=0.0,
        )


@github.action("get_code_scanning_alert")
class GetCodeScanningAlert(ActionHandler):
    """Get a single code scanning alert"""

    @handle_github_errors("get_code_scanning_alert")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = (
            f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}"
            f"/code-scanning/alerts/{inputs['alert_number']}"
        )
        alert = await _get_json(context, url)

        return ActionResult(data=_shape_code_scanning_alert(alert), cost_usd=0.0)


# ---------------------------------------------------------------------------
# Dependabot
# ---------------------------------------------------------------------------


@github.action("list_dependabot_alerts")
class ListDependabotAlerts(ActionHandler):
    """List Dependabot alerts for a repository or an organization"""

    @handle_github_errors("list_dependabot_alerts")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = _scoped_url(inputs.get("owner"), inputs.get("repo"), inputs.get("org"), "dependabot/alerts")

        params = _compact(
            {
                "state": inputs.get("state"),
                "severity": inputs.get("severity"),
                "ecosystem": inputs.get("ecosystem"),
                "package": inputs.get("package"),
                "scope": inputs.get("scope"),
                "manifest": inputs.get("manifest"),
                "sort": inputs.get("sort"),
                "direction": inputs.get("direction"),
            }
        )

        alerts = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), CURSOR_PAGE_MAX),
            max_pages=1,
        )

        return ActionResult(
            data=[_shape_dependabot_alert(alert) for alert in alerts],
            cost_usd=0.0,
        )


@github.action("get_dependabot_alert")
class GetDependabotAlert(ActionHandler):
    """Get a single Dependabot alert"""

    @handle_github_errors("get_dependabot_alert")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = (
            f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/dependabot/alerts/{inputs['alert_number']}"
        )
        alert = await _get_json(context, url)

        return ActionResult(data=_shape_dependabot_alert(alert), cost_usd=0.0)


# ---------------------------------------------------------------------------
# Secret scanning
# ---------------------------------------------------------------------------
# Both actions below hardcode ``hide_secret=true`` and run every alert through
# ``_shape_secret_scanning_alert``, which allow-lists non-credential metadata.
# There is deliberately no input to switch either safeguard off, and neither the
# raw response nor the shaped result is ever logged.


@github.action("list_secret_scanning_alerts")
class ListSecretScanningAlerts(ActionHandler):
    """List secret scanning alerts for a repository or an organization, never returning the leaked secrets"""

    @handle_github_errors("list_secret_scanning_alerts")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = _scoped_url(inputs.get("owner"), inputs.get("repo"), inputs.get("org"), "secret-scanning/alerts")

        params = _compact(
            {
                "state": inputs.get("state"),
                "secret_type": inputs.get("secret_type"),
                "resolution": inputs.get("resolution"),
                "validity": inputs.get("validity"),
                "sort": inputs.get("sort"),
                "direction": inputs.get("direction"),
            }
        )
        params["hide_secret"] = "true"  # nosec B105 - a flag that hides the secret, not a credential

        alerts = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), PAGED_MAX_RESULTS),
            max_pages=PAGED_MAX_PAGES,
        )

        return ActionResult(
            data=[_shape_secret_scanning_alert(alert) for alert in alerts],
            cost_usd=0.0,
        )


@github.action("get_secret_scanning_alert")
class GetSecretScanningAlert(ActionHandler):
    """Get a single secret scanning alert, never returning the leaked secret"""

    @handle_github_errors("get_secret_scanning_alert")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = (
            f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}"
            f"/secret-scanning/alerts/{inputs['alert_number']}"
        )
        alert = await _get_json(context, url, params={"hide_secret": "true"})  # nosec B105 - not a credential

        return ActionResult(data=_shape_secret_scanning_alert(alert), cost_usd=0.0)


# ---------------------------------------------------------------------------
# Code quality (public preview, github.com only)
# ---------------------------------------------------------------------------


@github.action("list_code_quality_findings")
class ListCodeQualityFindings(ActionHandler):
    """List GitHub Code Quality findings for a repository"""

    @handle_github_errors("list_code_quality_findings")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/code-quality/findings"

        params = _compact({"state": inputs.get("state"), "direction": inputs.get("direction")})

        findings = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), CURSOR_PAGE_MAX),
            max_pages=1,
        )

        return ActionResult(
            data=[_shape_code_quality_finding(finding) for finding in findings],
            cost_usd=0.0,
        )


@github.action("get_code_quality_finding")
class GetCodeQualityFinding(ActionHandler):
    """Get a single GitHub Code Quality finding"""

    @handle_github_errors("get_code_quality_finding")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = (
            f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}"
            f"/code-quality/findings/{inputs['finding_number']}"
        )
        finding = await _get_json(context, url)

        return ActionResult(data=_shape_code_quality_finding(finding), cost_usd=0.0)


# ---------------------------------------------------------------------------
# Security advisories
# ---------------------------------------------------------------------------


@github.action("list_global_security_advisories")
class ListGlobalSecurityAdvisories(ActionHandler):
    """Search the GitHub Advisory Database for global security advisories"""

    @handle_github_errors("list_global_security_advisories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/advisories"

        params = _compact(
            {
                "ghsa_id": inputs.get("ghsa_id"),
                "type": inputs.get("type"),
                "cve_id": inputs.get("cve_id"),
                "ecosystem": inputs.get("ecosystem"),
                "severity": inputs.get("severity"),
                "cwes": inputs.get("cwes"),
                "affects": inputs.get("affects"),
                "published": inputs.get("published"),
                "updated": inputs.get("updated"),
                "modified": inputs.get("modified"),
                "is_withdrawn": inputs.get("is_withdrawn"),
                "sort": inputs.get("sort"),
                "direction": inputs.get("direction"),
            }
        )

        advisories = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), CURSOR_PAGE_MAX),
            max_pages=1,
        )

        return ActionResult(
            data=[_shape_global_advisory(advisory) for advisory in advisories],
            cost_usd=0.0,
        )


@github.action("get_global_security_advisory")
class GetGlobalSecurityAdvisory(ActionHandler):
    """Get a single global security advisory by its GHSA ID"""

    @handle_github_errors("get_global_security_advisory")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/advisories/{inputs['ghsa_id']}"
        advisory = await _get_json(context, url)

        return ActionResult(data=_shape_global_advisory(advisory), cost_usd=0.0)


@github.action("list_repository_security_advisories")
class ListRepositorySecurityAdvisories(ActionHandler):
    """List security advisories authored in a repository, or across an organization"""

    @handle_github_errors("list_repository_security_advisories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = _scoped_url(inputs.get("owner"), inputs.get("repo"), inputs.get("org"), "security-advisories")

        params = _compact(
            {
                "state": inputs.get("state"),
                "sort": inputs.get("sort"),
                "direction": inputs.get("direction"),
            }
        )

        advisories = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=_resolve_limit(inputs.get("limit"), CURSOR_PAGE_MAX),
            max_pages=1,
        )

        return ActionResult(
            data=[_shape_repository_advisory(advisory) for advisory in advisories],
            cost_usd=0.0,
        )
