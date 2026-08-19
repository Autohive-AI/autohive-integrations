"""
GitHub integration - GitHub Actions workflow, run, job and artifact actions.

Three GitHub endpoints in this area answer ``302 Found`` with a signed URL that
lives for one minute, and that shapes the design of half this module:

- ``/actions/jobs/{job_id}/logs`` redirects to **plain text**.
- ``/actions/runs/{run_id}/logs`` redirects to a **ZIP archive**.
- ``/actions/artifacts/{artifact_id}/zip`` redirects to a **ZIP archive**.

``context.fetch`` runs on aiohttp with ``allow_redirects`` left at its default of
``True`` and exposes no way to turn that off, so the ``Location`` header is never
visible to us — the SDK hands back whatever the redirect target served. For the
plain-text case that is exactly what we want, so ``get_job_logs`` really does
return log text (tail-trimmed — a raw job log runs to megabytes).

For the two ZIP cases it is unusable: the SDK decodes any non-JSON body with
``await response.text()``, which raises ``UnicodeDecodeError`` on ZIP bytes
rather than returning them. So ``get_workflow_run_logs`` and
``download_workflow_run_artifact`` deliberately never request the archive. They
resolve the metadata endpoints instead and hand back the archive URL, its size
and its expiry, so the caller can download it themselves with their own token.
Returning a mangled archive would be worse than returning a link.

Reference: https://docs.github.com/en/rest/actions/workflows
Reference: https://docs.github.com/en/rest/actions/workflow-runs
Reference: https://docs.github.com/en/rest/actions/workflow-jobs
Reference: https://docs.github.com/en/rest/actions/artifacts
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("list_workflows")
class ListWorkflows(ActionHandler):
    """List GitHub Actions workflows"""

    @handle_github_errors("list_workflows")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        workflows = await GitHubAPI.list_workflows(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data=[
                {
                    "id": workflow["id"],
                    "name": workflow["name"],
                    "path": workflow["path"],
                    "state": workflow["state"],
                    "created_at": workflow["created_at"],
                    "updated_at": workflow["updated_at"],
                    "url": workflow["html_url"],
                }
                for workflow in workflows
            ],
            cost_usd=0.0,
        )


@github.action("get_workflow_runs")
class GetWorkflowRuns(ActionHandler):
    """Get workflow runs"""

    @handle_github_errors("get_workflow_runs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        runs = await GitHubAPI.get_workflow_runs(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["workflow_id"],
            status=inputs.get("status"),
            branch=inputs.get("branch"),
        )

        return ActionResult(
            data=[
                {
                    "id": run["id"],
                    "name": run["name"],
                    "workflow_id": run["workflow_id"],
                    "head_branch": run["head_branch"],
                    "head_sha": run["head_sha"],
                    "run_number": run["run_number"],
                    "event": run["event"],
                    "status": run["status"],
                    "conclusion": run["conclusion"],
                    "created_at": run["created_at"],
                    "updated_at": run["updated_at"],
                    "run_started_at": run.get("run_started_at"),
                    "run_attempt": run.get("run_attempt", 1),
                    "actor": {
                        "login": run["actor"]["login"],
                        "avatar_url": run["actor"]["avatar_url"],
                    },
                    "url": run["html_url"],
                }
                for run in runs
            ],
            cost_usd=0.0,
        )


# =============================================================================
# API HELPERS
# =============================================================================

# A single job log is routinely megabytes of text. Action output flows straight
# into a workflow context, so the body is tail-trimmed before it is returned.
_DEFAULT_TAIL_LINES = 500
_MAX_TAIL_LINES = 10000
_MAX_LOG_CHARS = 200000

# GitHub rejects a workflow_dispatch payload carrying more than 25 input keys.
_MAX_DISPATCH_INPUTS = 25

_RUN_LOGS_NOTE = (
    "GitHub serves workflow run logs only as a ZIP archive behind a signed redirect that expires after one "
    "minute, and this integration cannot return binary payloads. Download logs_archive_url yourself with a "
    "GitHub token, or call Get Job Logs with one of the job IDs above to read log text directly."
)

_ARTIFACT_NOTE = (
    "GitHub serves artifacts only as a ZIP archive behind a signed redirect that expires after one minute, and "
    "this integration cannot return binary payloads. Download archive_download_url yourself with a GitHub token "
    "— it is an api.github.com URL and needs the same authentication as any other REST call."
)

_ARTIFACT_EXPIRED_NOTE = (
    "This artifact has passed its retention date and has been deleted by GitHub, so archive_download_url will "
    "answer 410 Gone. Re-run the workflow to produce a fresh artifact."
)


def _actions_url(owner: str, repo: str, *segments: Any) -> str:
    """Build a URL under ``/repos/{owner}/{repo}/actions``."""
    suffix = "/".join(str(segment) for segment in segments)
    return f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/actions/{suffix}"


def _workflow_ref(workflow_id: Any) -> str:
    """Percent-encode a workflow identifier for use in a path segment.

    ``workflow_id`` is either the numeric workflow ID or the workflow's filename
    ("ci.yml"). Both are safe characters, so this is normally a no-op — it exists
    so an unexpected name can never break out of its path segment.
    """
    return quote(str(workflow_id), safe="")


def _run_html_url(owner: str, repo: str, run_id: Any) -> str:
    """The github.com page for a workflow run.

    The rerun and cancel endpoints answer with an empty body, so the link back to
    the run is rebuilt from the identifiers the caller already supplied.
    """
    return f"https://github.com/{owner}/{repo}/actions/runs/{run_id}"


def _as_dict(payload: Any) -> Dict[str, Any]:
    """Coerce a response body to a dict.

    Dispatch, rerun and cancel answer 204/201/202 with an empty or ``{}`` body,
    which the SDK surfaces as ``None`` or ``""``. Calling ``.get()`` on either
    raises, so every write action funnels its response through here first.
    """
    return payload if isinstance(payload, dict) else {}


def _ms_to_minutes(milliseconds: Optional[int]) -> float:
    """Convert milliseconds to minutes, rounded to two decimal places."""
    return round((milliseconds or 0) / 60000, 2)


def _clamp_tail_lines(value: Any) -> int:
    """Normalise the ``tail_lines`` input into a sane, bounded line count."""
    if value is None:
        return _DEFAULT_TAIL_LINES
    try:
        requested = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_TAIL_LINES
    return max(1, min(requested, _MAX_TAIL_LINES))


def _tail(text: str, tail_lines: int) -> Dict[str, Any]:
    """Keep the last ``tail_lines`` lines of ``text``, with truncation metadata.

    A secondary character cap guards against a log whose "lines" are single
    enormous blobs (minified output, base64 dumps), which a line count alone
    would not bound.
    """
    lines = text.splitlines()
    total_lines = len(lines)
    kept = lines[-tail_lines:] if tail_lines < total_lines else lines
    body = "\n".join(kept)

    if len(body) > _MAX_LOG_CHARS:
        body = body[-_MAX_LOG_CHARS:]
        kept = body.splitlines()

    return {
        "logs": body,
        "total_lines": total_lines,
        "returned_lines": len(kept),
        "truncated": len(kept) < total_lines,
    }


def _shape_actor(actor: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Flatten a GitHub user to login/avatar. Null on since-deleted accounts."""
    if not actor:
        return None
    return {"login": actor.get("login"), "avatar_url": actor.get("avatar_url")}


def _shape_run(run: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a workflow run payload into the integration's run output."""
    head_commit = run.get("head_commit")
    commit_author = (head_commit or {}).get("author") or {}

    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "display_title": run.get("display_title"),
        "workflow_id": run.get("workflow_id"),
        "path": run.get("path"),
        "head_branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"),
        "run_number": run.get("run_number"),
        "run_attempt": run.get("run_attempt", 1),
        "event": run.get("event"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "run_started_at": run.get("run_started_at"),
        "actor": _shape_actor(run.get("actor")),
        "triggering_actor": _shape_actor(run.get("triggering_actor")),
        "head_commit": (
            {
                "id": head_commit.get("id"),
                "message": head_commit.get("message"),
                "author": commit_author.get("name"),
            }
            if head_commit
            else None
        ),
        "logs_archive_url": run.get("logs_url"),
        "url": run.get("html_url"),
    }


def _shape_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a workflow job payload, including its per-step breakdown."""
    return {
        "id": job.get("id"),
        "run_id": job.get("run_id"),
        "run_attempt": job.get("run_attempt"),
        "name": job.get("name"),
        "workflow_name": job.get("workflow_name"),
        "head_branch": job.get("head_branch"),
        "head_sha": job.get("head_sha"),
        "status": job.get("status"),
        "conclusion": job.get("conclusion"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "runner_name": job.get("runner_name"),
        "labels": job.get("labels") or [],
        "steps": [
            {
                "number": step.get("number"),
                "name": step.get("name"),
                "status": step.get("status"),
                "conclusion": step.get("conclusion"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
            }
            for step in (job.get("steps") or [])
        ],
        "url": job.get("html_url"),
    }


def _shape_job_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal job identity — enough to feed a follow-up Get Job Logs call."""
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "status": job.get("status"),
        "conclusion": job.get("conclusion"),
    }


def _shape_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Shape an artifact payload. ``workflow_run`` is nullable on GitHub's side."""
    source_run = artifact.get("workflow_run")

    return {
        "id": artifact.get("id"),
        "name": artifact.get("name"),
        "size_in_bytes": artifact.get("size_in_bytes"),
        "expired": artifact.get("expired"),
        "created_at": artifact.get("created_at"),
        "updated_at": artifact.get("updated_at"),
        "expires_at": artifact.get("expires_at"),
        "digest": artifact.get("digest"),
        "archive_download_url": artifact.get("archive_download_url"),
        "url": artifact.get("url"),
        "workflow_run": (
            {
                "id": source_run.get("id"),
                "head_branch": source_run.get("head_branch"),
                "head_sha": source_run.get("head_sha"),
            }
            if source_run
            else None
        ),
    }


async def _get_run(
    context: ExecutionContext,
    owner: str,
    repo: str,
    run_id: Any,
    exclude_pull_requests: Optional[bool] = None,
) -> Dict[str, Any]:
    """GET /repos/{owner}/{repo}/actions/runs/{run_id}"""
    url = _actions_url(owner, repo, "runs", run_id)
    params = {"exclude_pull_requests": "true"} if exclude_pull_requests else None
    return _as_dict((await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))).data)


async def _dispatch_workflow(
    context: ExecutionContext,
    owner: str,
    repo: str,
    workflow_id: Any,
    ref: str,
    workflow_inputs: Optional[Dict[str, Any]] = None,
    return_run_details: bool = False,
) -> Dict[str, Any]:
    """POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches

    Answers ``204 No Content`` by default. Passing ``return_run_details`` turns it
    into a ``200`` carrying ``workflow_run_id`` / ``run_url`` / ``html_url``; the
    flag is only sent when explicitly requested so the default path stays on the
    long-stable behaviour.
    """
    url = _actions_url(owner, repo, "workflows", _workflow_ref(workflow_id), "dispatches")
    body: Dict[str, Any] = {"ref": ref}
    if workflow_inputs:
        body["inputs"] = workflow_inputs
    if return_run_details:
        body["return_run_details"] = True

    return _as_dict((await context.fetch(url, method="POST", json=body, headers=GitHubAPI.get_headers(context))).data)


async def _rerun_run(
    context: ExecutionContext,
    owner: str,
    repo: str,
    run_id: Any,
    endpoint: str,
    enable_debug_logging: Optional[bool] = None,
) -> Dict[str, Any]:
    """POST /repos/{owner}/{repo}/actions/runs/{run_id}/{rerun|rerun-failed-jobs} — 201, empty body."""
    url = _actions_url(owner, repo, "runs", run_id, endpoint)
    body: Dict[str, Any] = {}
    if enable_debug_logging is not None:
        body["enable_debug_logging"] = bool(enable_debug_logging)

    return _as_dict((await context.fetch(url, method="POST", json=body, headers=GitHubAPI.get_headers(context))).data)


async def _cancel_run(context: ExecutionContext, owner: str, repo: str, run_id: Any) -> Dict[str, Any]:
    """POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel — 202, empty body."""
    url = _actions_url(owner, repo, "runs", run_id, "cancel")
    return _as_dict((await context.fetch(url, method="POST", headers=GitHubAPI.get_headers(context))).data)


async def _list_run_jobs(
    context: ExecutionContext,
    owner: str,
    repo: str,
    run_id: Any,
    job_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs"""
    url = _actions_url(owner, repo, "runs", run_id, "jobs")
    params: Dict[str, Any] = {}
    if job_filter:
        params["filter"] = job_filter

    return await GitHubAPI.paginated_fetch(context, url, params=params, data_key="jobs", limit=limit)


async def _fetch_job_log_text(context: ExecutionContext, owner: str, repo: str, job_id: Any) -> str:
    """GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs

    Answers 302 to a signed, one-minute URL serving ``text/plain``. aiohttp follows
    the redirect (dropping the Authorization header cross-origin, which is what the
    signed URL expects), so what arrives here is the log body itself. GitHub emits a
    UTF-8 BOM at the front of it.
    """
    url = _actions_url(owner, repo, "jobs", job_id, "logs")
    payload = (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data
    if not payload:
        return ""
    return str(payload).lstrip("\ufeff")


async def _get_artifact(context: ExecutionContext, owner: str, repo: str, artifact_id: Any) -> Dict[str, Any]:
    """GET /repos/{owner}/{repo}/actions/artifacts/{artifact_id}"""
    url = _actions_url(owner, repo, "artifacts", artifact_id)
    return _as_dict((await context.fetch(url, headers=GitHubAPI.get_headers(context))).data)


async def _list_run_artifacts(
    context: ExecutionContext,
    owner: str,
    repo: str,
    run_id: Any,
    name: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"""
    url = _actions_url(owner, repo, "runs", run_id, "artifacts")
    params: Dict[str, Any] = {}
    if name:
        params["name"] = name

    return await GitHubAPI.paginated_fetch(context, url, params=params, data_key="artifacts", limit=limit)


async def _get_run_timing(context: ExecutionContext, owner: str, repo: str, run_id: Any) -> Dict[str, Any]:
    """GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing"""
    url = _actions_url(owner, repo, "runs", run_id, "timing")
    return _as_dict((await context.fetch(url, headers=GitHubAPI.get_headers(context))).data)


async def _delete_run_logs(context: ExecutionContext, owner: str, repo: str, run_id: Any) -> None:
    """DELETE /repos/{owner}/{repo}/actions/runs/{run_id}/logs — 204, no body."""
    url = _actions_url(owner, repo, "runs", run_id, "logs")
    await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("get_workflow_run")
class GetWorkflowRun(ActionHandler):
    """Get a single workflow run by its run ID"""

    @handle_github_errors("get_workflow_run")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        run = await _get_run(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["run_id"],
            exclude_pull_requests=inputs.get("exclude_pull_requests"),
        )

        return ActionResult(data=_shape_run(run), cost_usd=0.0)


@github.action("run_workflow")
class RunWorkflow(ActionHandler):
    """Trigger a workflow_dispatch run of a workflow on a branch or tag"""

    @handle_github_errors("run_workflow")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        workflow_inputs = inputs.get("inputs") or {}
        if len(workflow_inputs) > _MAX_DISPATCH_INPUTS:
            raise ValueError(
                f"A workflow_dispatch event accepts at most {_MAX_DISPATCH_INPUTS} inputs, "
                f"but {len(workflow_inputs)} were supplied."
            )

        return_run_details = bool(inputs.get("return_run_details"))
        payload = await _dispatch_workflow(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["workflow_id"],
            inputs["ref"],
            workflow_inputs=workflow_inputs,
            return_run_details=return_run_details,
        )

        run_id = payload.get("workflow_run_id")
        message = (
            f"Dispatched '{inputs['workflow_id']}' on '{inputs['ref']}'."
            if run_id
            else (
                f"Dispatched '{inputs['workflow_id']}' on '{inputs['ref']}'. GitHub answered 204 No Content, so no "
                "run ID is available — set return_run_details to true, or use Get Workflow Runs to find the new run."
            )
        )

        return ActionResult(
            data={
                "dispatched": True,
                "workflow_id": str(inputs["workflow_id"]),
                "ref": inputs["ref"],
                "inputs": workflow_inputs,
                "run_id": run_id,
                "run_api_url": payload.get("run_url"),
                "url": payload.get("html_url"),
                "message": message,
            },
            cost_usd=0.0,
        )


@github.action("rerun_workflow_run")
class RerunWorkflowRun(ActionHandler):
    """Re-run every job in a workflow run"""

    @handle_github_errors("rerun_workflow_run")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _rerun_run(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["run_id"],
            "rerun",
            enable_debug_logging=inputs.get("enable_debug_logging"),
        )

        return ActionResult(
            data={
                "rerun_requested": True,
                "run_id": inputs["run_id"],
                "scope": "all_jobs",
                "url": _run_html_url(inputs["owner"], inputs["repo"], inputs["run_id"]),
            },
            cost_usd=0.0,
        )


@github.action("rerun_failed_jobs")
class RerunFailedJobs(ActionHandler):
    """Re-run only the failed jobs of a workflow run"""

    @handle_github_errors("rerun_failed_jobs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _rerun_run(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["run_id"],
            "rerun-failed-jobs",
            enable_debug_logging=inputs.get("enable_debug_logging"),
        )

        return ActionResult(
            data={
                "rerun_requested": True,
                "run_id": inputs["run_id"],
                "scope": "failed_jobs",
                "url": _run_html_url(inputs["owner"], inputs["repo"], inputs["run_id"]),
            },
            cost_usd=0.0,
        )


@github.action("cancel_workflow_run")
class CancelWorkflowRun(ActionHandler):
    """Cancel a queued or in-progress workflow run"""

    @handle_github_errors("cancel_workflow_run")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _cancel_run(context, inputs["owner"], inputs["repo"], inputs["run_id"])

        return ActionResult(
            data={
                "cancelled": True,
                "run_id": inputs["run_id"],
                "url": _run_html_url(inputs["owner"], inputs["repo"], inputs["run_id"]),
                "message": "Cancellation accepted. GitHub stops the run asynchronously, so its status may still "
                "read in_progress for a short while.",
            },
            cost_usd=0.0,
        )


@github.action("list_workflow_jobs")
class ListWorkflowJobs(ActionHandler):
    """List the jobs of a workflow run, with each job's step-by-step outcome"""

    @handle_github_errors("list_workflow_jobs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        jobs = await _list_run_jobs(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["run_id"],
            job_filter=inputs.get("filter"),
            limit=inputs.get("limit"),
        )

        return ActionResult(data=[_shape_job(job) for job in jobs], cost_usd=0.0)


@github.action("get_job_logs")
class GetJobLogs(ActionHandler):
    """Read the plain-text log of one workflow job, trimmed to its last N lines"""

    @handle_github_errors("get_job_logs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        tail_lines = _clamp_tail_lines(inputs.get("tail_lines"))
        log_text = await _fetch_job_log_text(context, inputs["owner"], inputs["repo"], inputs["job_id"])
        tail = _tail(log_text, tail_lines)

        return ActionResult(
            data={
                "job_id": inputs["job_id"],
                "tail_lines": tail_lines,
                "logs": tail["logs"],
                "total_lines": tail["total_lines"],
                "returned_lines": tail["returned_lines"],
                "truncated": tail["truncated"],
            },
            cost_usd=0.0,
        )


@github.action("get_workflow_run_logs")
class GetWorkflowRunLogs(ActionHandler):
    """Locate a workflow run's log archive and list its jobs — returns a URL, never the ZIP itself"""

    @handle_github_errors("get_workflow_run_logs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        run = await _get_run(context, inputs["owner"], inputs["repo"], inputs["run_id"])
        jobs = await _list_run_jobs(context, inputs["owner"], inputs["repo"], inputs["run_id"])
        shaped_run = _shape_run(run)

        return ActionResult(
            data={
                "run_id": shaped_run["id"],
                "name": shaped_run["name"],
                "status": shaped_run["status"],
                "conclusion": shaped_run["conclusion"],
                "run_attempt": shaped_run["run_attempt"],
                "url": shaped_run["url"],
                "logs_archive_url": (
                    shaped_run["logs_archive_url"]
                    or _actions_url(inputs["owner"], inputs["repo"], "runs", inputs["run_id"], "logs")
                ),
                "archive_returned": False,
                "jobs": [_shape_job_summary(job) for job in jobs],
                "note": _RUN_LOGS_NOTE,
            },
            cost_usd=0.0,
        )


@github.action("list_workflow_run_artifacts")
class ListWorkflowRunArtifacts(ActionHandler):
    """List the artifacts a workflow run produced, with sizes and expiry dates"""

    @handle_github_errors("list_workflow_run_artifacts")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        artifacts = await _list_run_artifacts(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["run_id"],
            name=inputs.get("name"),
            limit=inputs.get("limit"),
        )

        return ActionResult(data=[_shape_artifact(artifact) for artifact in artifacts], cost_usd=0.0)


@github.action("download_workflow_run_artifact")
class DownloadWorkflowRunArtifact(ActionHandler):
    """Resolve an artifact's download URL, size and expiry — returns a link, never the ZIP itself"""

    @handle_github_errors("download_workflow_run_artifact")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        artifact = await _get_artifact(context, inputs["owner"], inputs["repo"], inputs["artifact_id"])
        shaped_artifact = _shape_artifact(artifact)
        shaped_artifact["archive_returned"] = False
        shaped_artifact["note"] = _ARTIFACT_EXPIRED_NOTE if shaped_artifact["expired"] else _ARTIFACT_NOTE

        return ActionResult(data=shaped_artifact, cost_usd=0.0)


@github.action("get_workflow_run_usage")
class GetWorkflowRunUsage(ActionHandler):
    """Get the billable runner minutes a workflow run consumed, broken down by operating system"""

    @handle_github_errors("get_workflow_run_usage")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        timing = await _get_run_timing(context, inputs["owner"], inputs["repo"], inputs["run_id"])
        billable = timing.get("billable") or {}

        breakdown = []
        for os_name, stats in billable.items():
            usage = stats or {}
            breakdown.append(
                {
                    "os": os_name,
                    "jobs": usage.get("jobs"),
                    "total_ms": usage.get("total_ms"),
                    "billable_minutes": _ms_to_minutes(usage.get("total_ms")),
                    "job_runs": [
                        {"job_id": job_run.get("job_id"), "duration_ms": job_run.get("duration_ms")}
                        for job_run in (usage.get("job_runs") or [])
                    ],
                }
            )

        total_billable_ms = sum(entry["total_ms"] or 0 for entry in breakdown)

        return ActionResult(
            data={
                "run_id": inputs["run_id"],
                "run_duration_ms": timing.get("run_duration_ms"),
                "run_duration_minutes": _ms_to_minutes(timing.get("run_duration_ms")),
                "total_billable_ms": total_billable_ms,
                "total_billable_minutes": _ms_to_minutes(total_billable_ms),
                "billable": breakdown,
            },
            cost_usd=0.0,
        )


@github.action("delete_workflow_run_logs")
class DeleteWorkflowRunLogs(ActionHandler):
    """Delete all log files for a workflow run"""

    @handle_github_errors("delete_workflow_run_logs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _delete_run_logs(context, inputs["owner"], inputs["repo"], inputs["run_id"])

        return ActionResult(data={"deleted": True, "run_id": inputs["run_id"]}, cost_usd=0.0)
