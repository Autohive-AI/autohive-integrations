"""Agno Data Agent — Autohive integration for database Q&A via the Agno AgentOS API."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
    ExecutionContext,
    FetchResponse,
    HTTPError,
    Integration,
    ValidationError,
)

agno_agent = Integration.load()

RETRYABLE_STATUSES = {502, 503, 504}
MAX_ATTEMPTS = 3


def _extract_credentials(context: ExecutionContext) -> tuple[str, str, str]:
    """Return (api_url, api_token, agent_id) from context, raising ValidationError on missing fields."""
    credentials = context.auth.get("credentials", {})
    api_url = credentials.get("api_url", "")
    if not api_url:
        raise ValidationError("Missing required credential: api_url")
    agent_id = credentials.get("agent_id", "")
    if not agent_id:
        raise ValidationError("Missing required credential: agent_id")
    return api_url.rstrip("/"), credentials.get("api_token", ""), agent_id


def _parse_sse_response(body: Any) -> str:
    """Extract the agent's final answer from an AgentOS SSE response body.

    Prefers the ``RunCompleted`` event's ``content`` (the final, fully-formed
    answer). Falls back to concatenating streamed content chunks if no terminal
    event is present — Agno emits these as ``RunContent`` by default (older
    deployments use ``RunResponse``/``RunResponseContent``), and ``RunCompleted``
    is only guaranteed when all events are streamed.
    """
    if not isinstance(body, str):
        return ""

    completed_content: Optional[str] = None
    streamed_chunks: List[str] = []

    for block in body.replace("\r\n", "\n").split("\n\n"):
        # Parse both SSE fields per block: ``event:`` (canonical SSE event type)
        # and ``data:`` (the JSON payload). The event type may live in either
        # the SSE line or the payload's ``event`` field — Agno's documented
        # wire format uses the SSE line, while older fixtures embed it in JSON.
        event_line: Optional[str] = None
        data_lines: List[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_line = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())

        if not data_lines:
            continue

        try:
            payload = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        event = payload.get("event") or event_line
        content = payload.get("content")
        if not isinstance(content, str):
            continue

        if event == "RunCompleted":
            completed_content = content
        elif event in {"RunContent", "RunResponse", "RunResponseContent"}:
            streamed_chunks.append(content)

    if completed_content:
        return completed_content
    if streamed_chunks:
        return "".join(streamed_chunks)
    return ""


def _looks_like_sse(body: str) -> bool:
    """True if the body carries SSE framing (at least one ``data:`` line)."""
    return any(line.startswith("data:") for line in body.replace("\r\n", "\n").splitlines())


def _extract_answer(body: Any) -> str:
    """Pull the agent's answer from an AgentOS response body.

    The normal path is an SSE stream (``stream=true``). Falls back to a plain
    JSON or text body, since some AgentOS deployments or proxies may answer with
    a regular payload despite ``stream=true`` — without this fallback those
    valid answers would be discarded.

    A body that *is* SSE-framed but yielded no content (e.g. only ``RunStarted``)
    returns ``""`` rather than the raw framing, so the caller can fall back to
    the empty-response default.
    """
    sse_content = _parse_sse_response(body)
    if sse_content:
        return sse_content
    if isinstance(body, dict):
        candidate = body.get("content") or body.get("message")
        return candidate if isinstance(candidate, str) else ""
    if isinstance(body, str) and not _looks_like_sse(body):
        return body
    return ""


async def _fetch_with_gateway_retry(context: ExecutionContext, url: str, **kwargs: Any) -> FetchResponse:
    """Call ``context.fetch`` with retries on transient gateway/proxy 5xx responses.

    The SDK only retries client-side network errors; gateway 5xx responses (502/503/504)
    are surfaced immediately. AgentOS deployments typically sit behind a load balancer
    whose idle timeout can produce transient 504s, so retry those here with
    exponential backoff.
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await context.fetch(url, **kwargs)
        except HTTPError as exc:
            if exc.status in RETRYABLE_STATUSES and attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(2**attempt)
                continue
            raise


@agno_agent.action("ask_agent")
class AskAgentHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        # query is required in the schema and validated by the SDK before this runs;
        # the empty-string guard catches the schema's lack of a minLength constraint.
        query = inputs["query"]
        if not query:
            raise ValidationError("Missing required input: query")

        api_url, api_token, agent_id = _extract_credentials(context)

        url = f"{api_url}/agents/{agent_id}/runs"
        headers = {"Accept": "text/event-stream"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        # stream=true so AgentOS emits SSE events while the agent works; each event
        # resets the upstream load balancer's idle timer and prevents 504s on long queries.
        try:
            response = await _fetch_with_gateway_retry(
                context,
                url,
                method="POST",
                content_type="application/x-www-form-urlencoded",
                data={"message": query, "stream": "true"},
                headers=headers,
                timeout=120,
            )
        except HTTPError as exc:
            # Gateway 5xx that survived all retries — service-availability problem,
            # not a code defect. Surface a clean user-facing error instead of letting
            # the HTTPError (with its full HTML body) propagate into error tracking.
            if exc.status in RETRYABLE_STATUSES:
                return ActionError(
                    message=(
                        f"The agent service is temporarily unavailable (HTTP {exc.status}). "
                        "The request was retried but did not succeed — please try again shortly."
                    )
                )
            raise

        content = _extract_answer(response.data) or "No response from agent."
        return ActionResult(data={"response": str(content)})


@agno_agent.connected_account()
class AgnoConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        api_url, api_token, agent_id = _extract_credentials(context)

        headers = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        await context.fetch(
            f"{api_url}/health",
            method="GET",
            headers=headers,
            timeout=10,
        )

        return ConnectedAccountInfo(
            username=f"{agent_id} @ {api_url}",
        )
