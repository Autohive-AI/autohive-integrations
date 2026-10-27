"""Agno Data Agent — Autohive integration for database Q&A via the Agno AgentOS API."""

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp
from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
    ExecutionContext,
    HTTPError,
    Integration,
    ValidationError,
)

agno_agent = Integration.load()

RETRYABLE_STATUSES = {502, 503, 504}
MAX_ATTEMPTS = 3

# Memory bounds for reading the run stream. AgentOS always streams every run event,
# and each ``ToolCallCompleted`` event carries the full result of the SQL the agent
# ran — easily many MB for a "return the full table" question. Buffering that whole
# body (as ``context.fetch`` does) OOM-killed the Lambda, so the stream is read in
# chunks and only answer-bearing events are ever held in memory.
STREAM_CHUNK_BYTES = 64 * 1024
MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 4 * 1024
UTF8_BOM = b"\xef\xbb\xbf"
ANSWER_EVENTS = {"RunCompleted", "RunContent", "RunResponse", "RunResponseContent"}
# SSE lines end in CRLF, LF or a bare CR.
LINE_END = re.compile(rb"\r\n?|\n")


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


class AnswerTooLargeError(Exception):
    """The agent's answer exceeded ``MAX_EVENT_BYTES`` and could not be kept whole."""


class _SSEAnswerCollector:
    """Incremental AgentOS SSE parser that keeps only the agent's answer in memory.

    Fed raw byte chunks as they arrive. Prefers the ``RunCompleted`` event's
    ``content`` (the final answer) and falls back to concatenating streamed chunks —
    ``RunContent`` by default, ``RunResponse``/``RunResponseContent`` on older
    deployments. The event type is read from the payload's ``event`` field or, failing
    that, the SSE ``event:`` line.

    Once the body is known to be SSE, lines of an event whose ``event:`` line names a
    non-answer type (tool results, reasoning, metrics) are discarded without being
    buffered or parsed, so for those the ``event:`` line decides. Events typed only in
    their JSON are buffered up to ``MAX_EVENT_BYTES`` and dropped beyond that, since
    their type is unknown. An answer
    typed by its ``event:`` line (as Agno sends them) that outgrows the bound raises
    ``AnswerTooLargeError`` rather than being cut short.

    The body is SSE once a ``data:`` line appears. Until then, ``event:``, ``id:``,
    ``retry:``, comment and blank lines are held; any other line, or the end of the body,
    means it is a plain answer and is returned as text (also bounded by ``MAX_EVENT_BYTES``).
    A body of only comment and blank lines (e.g. keep-alives) has no answer.
    """

    SSE_PREAMBLE_FIELDS = (b"event:", b"id:", b"retry:", b":")
    DATA_PREFIXES = (b"data:", UTF8_BOM + b"data:")

    def __init__(self) -> None:
        self._line = bytearray()
        # Discarding the current line; _skipped_text records whether it had any content,
        # since a skipped blank line still ends its event.
        self._skip = False
        self._skipped_text = False
        # The last chunk ended in CR, so a leading LF in the next one completes that CRLF.
        self._after_cr = False
        self._mode: Optional[str] = None  # "sse" or "raw" once decided; raw text is held until then
        self._raw = bytearray()
        self._raw_overflow = False
        self._raw_has_text = False  # a held line other than a comment or blank line
        self._event_type: Optional[str] = None
        self._data: List[str] = []
        self._data_bytes = 0  # above MAX_EVENT_BYTES marks the current event as dropped
        self._completed: Optional[str] = None
        self._chunks: List[str] = []
        self._chunk_bytes = 0  # above MAX_EVENT_BYTES means the answer was too large

    def feed(self, chunk: bytes) -> None:
        view = memoryview(chunk)
        start = 0
        if self._after_cr and chunk[:1] == b"\n":
            start = 1
        self._after_cr = False
        while start < len(chunk):
            if self._mode == "raw":
                self._append_raw(view[start:])
                if self._raw_overflow:
                    # The plain answer can no longer be returned whole; stop reading now.
                    raise AnswerTooLargeError()
                return
            match = LINE_END.search(chunk, start)
            stop = match.start() if match else len(chunk)
            if self._skip:
                # Don't slice: skipped lines can be tens of MB.
                self._skipped_text = self._skipped_text or stop > start
            else:
                self._line += view[start:stop]
                if len(self._line) > MAX_EVENT_BYTES:
                    if self._mode is None and not self._line.startswith(self.DATA_PREFIXES):
                        # An oversized line of a plain body.
                        raise AnswerTooLargeError()
                    self._mode = "sse"
                    self._raw.clear()
                    self._line.clear()
                    self._skip = self._skipped_text = True
                    self._data_bytes = MAX_EVENT_BYTES + 1
            if match is None:
                return
            self._end_line(newline=True)
            start = match.end()
            self._after_cr = start == len(chunk) and match.group() == b"\r"

    def _append_raw(self, data: Any) -> None:
        room = MAX_EVENT_BYTES - len(self._raw)
        if len(data) > room:
            self._raw_overflow = True
        self._raw += memoryview(data)[:room]

    def _end_line(self, newline: bool) -> None:
        if self._skip:
            if not self._skipped_text:
                self._dispatch()
        else:
            self._handle_line(newline)
        self._line.clear()
        self._skipped_text = False
        # A line inside an event already typed as non-answer is never needed.
        self._skip = self._mode == "sse" and self._event_type is not None and self._event_type not in ANSWER_EVENTS

    def _handle_line(self, newline: bool) -> None:
        line = self._line
        if self._mode is None:
            if line.startswith(UTF8_BOM):
                del line[: len(UTF8_BOM)]
            if line.startswith(b"data:"):
                self._mode = "sse"
                self._raw.clear()
            else:
                # Undecided: hold the text. SSE preamble and blank lines keep it undecided (and
                # an event: line still types the coming event); any other line makes it plain.
                self._append_raw(line)
                if newline:
                    self._append_raw(b"\n")
                if line.strip() and not line.startswith(b":"):
                    self._raw_has_text = True
                    if not line.startswith(self.SSE_PREAMBLE_FIELDS):
                        self._mode = "raw"
                        return
        if not line:
            self._dispatch()
        elif line.startswith(b"event:"):
            self._event_type = line[len(b"event:") :].decode("utf-8", errors="replace").strip()
        elif line.startswith(b"data:"):
            self._data_bytes += len(line)
            if self._data_bytes > MAX_EVENT_BYTES:
                self._data.clear()
            else:
                self._data.append(line[len(b"data:") :].decode("utf-8", errors="replace").lstrip())

    def _dispatch(self) -> None:
        event_line, data, dropped = self._event_type, self._data, self._data_bytes > MAX_EVENT_BYTES
        self._event_type, self._data, self._data_bytes = None, [], 0
        if dropped and event_line in ANSWER_EVENTS:
            # Not falling back to the chunks for a dropped RunCompleted: a post-hook may have rewritten it.
            self._chunk_bytes = MAX_EVENT_BYTES + 1
        # A non-answer event: line decides even when its lines weren't skipped (the first event).
        if dropped or not data or (event_line is not None and event_line not in ANSWER_EVENTS):
            return
        try:
            payload = json.loads(data[0] if len(data) == 1 else "\n".join(data))
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        event = payload.get("event") or event_line
        content = payload.get("content")
        if not isinstance(content, str):
            return
        if event == "RunCompleted":
            self._completed = content
        elif event in ANSWER_EVENTS and self._chunk_bytes <= MAX_EVENT_BYTES:
            self._chunk_bytes += len(content.encode("utf-8", "surrogatepass"))
            if self._chunk_bytes > MAX_EVENT_BYTES:
                # Bound memory like any single event, but report it instead of cutting the answer.
                self._chunks.clear()
            else:
                self._chunks.append(content)

    def finish(self) -> str:
        """Flush a trailing event with no closing blank line and return the answer.

        An SSE body with no answer content (e.g. only ``RunStarted``) returns ``""``.
        Raises ``AnswerTooLargeError`` if the answer outgrew ``MAX_EVENT_BYTES``.
        """
        if self._line:
            self._end_line(newline=False)
        if self._mode != "sse":
            if self._raw_overflow:
                raise AnswerTooLargeError()
            # Plain text, or only SSE preamble and blank lines: kept unless they are just comments.
            return self._raw.decode("utf-8", errors="replace") if self._raw_has_text else ""
        self._dispatch()
        if self._completed:
            return self._completed
        if self._chunk_bytes > MAX_EVENT_BYTES:
            raise AnswerTooLargeError()
        return "".join(self._chunks)


def _extract_answer(body: Any) -> str:
    """Pull the agent's answer from a JSON response body read in full.

    Some deployments or proxies answer with plain JSON despite ``stream=true``. A body
    labelled JSON that doesn't parse (passed as bytes), or a JSON string, is handled as
    text by the stream parser, so SSE text still yields its answer and plain text is
    returned as-is.
    """
    if isinstance(body, dict):
        candidate = body.get("content") or body.get("message")
        return candidate if isinstance(candidate, str) else ""
    if isinstance(body, str):  # a JSON string
        body = body.encode("utf-8")
    if not isinstance(body, (bytes, bytearray)):
        return ""
    collector = _SSEAnswerCollector()
    collector.feed(body)
    return collector.finish()


async def _read_capped(content: aiohttp.StreamReader, limit: int) -> bytearray:
    """Read until EOF or ``limit`` bytes; a single ``read(n)`` may return less than n."""
    body = bytearray()
    while len(body) < limit:
        chunk = await content.read(limit - len(body))
        if not chunk:
            break
        body += chunk
    return body


async def _post_run(url: str, data: Dict[str, str], headers: Dict[str, str], timeout: int) -> str:
    """POST an agent run and return its answer, reading the response incrementally.

    Uses aiohttp directly because ``context.fetch`` reads the entire body into
    memory before returning. Non-2xx responses raise ``HTTPError`` (status plus a
    capped body), matching what ``context.fetch`` did.
    """
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(url, data=data, headers=headers) as response:
            if response.status >= 400:
                # The body is only diagnostic; losing it mustn't hide a retryable gateway status.
                try:
                    body = await _read_capped(response.content, MAX_ERROR_BODY_BYTES)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    body = bytearray()
                raise HTTPError(response.status, body.decode("utf-8", errors="replace"))

            if response.content_type == "application/json":
                raw = await _read_capped(response.content, MAX_EVENT_BYTES + 1)
                if len(raw) > MAX_EVENT_BYTES:
                    raise AnswerTooLargeError()
                try:
                    payload: Any = json.loads(raw)
                except ValueError:  # invalid JSON or invalid UTF-8
                    payload = raw
                return _extract_answer(payload)

            # The SSE stream, or a plain text answer; the collector tells them apart.
            collector = _SSEAnswerCollector()
            async for chunk in response.content.iter_chunked(STREAM_CHUNK_BYTES):
                collector.feed(chunk)
            return collector.finish()


async def _with_gateway_retry(request: Callable[[], Awaitable[str]]) -> str:
    """Run ``request`` with retries on transient gateway/proxy 5xx responses.

    AgentOS deployments typically sit behind a load balancer whose idle timeout
    can produce transient 504s, so retry those with exponential backoff. Connection
    failures (request never reached the server) are retried the same way. The SDK's
    own fetch retry can't be used: it buffers the whole body and doesn't retry 5xx.
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await request()
        except (HTTPError, aiohttp.ClientConnectorError) as exc:
            retryable = not isinstance(exc, HTTPError) or exc.status in RETRYABLE_STATUSES
            if not retryable or attempt == MAX_ATTEMPTS - 1:
                raise
            await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")  # pragma: no cover


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
            content = await _with_gateway_retry(
                lambda: _post_run(url, data={"message": query, "stream": "true"}, headers=headers, timeout=120)
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
        except (aiohttp.InvalidURL, aiohttp.NonHttpUrlClientError):
            return ActionError(message="The API URL is not a valid http(s) URL — check it in the connection settings.")
        except aiohttp.ClientConnectorError:
            return ActionError(
                message="Could not reach the agent service after several attempts — check the API URL and try again."
            )
        except AnswerTooLargeError:
            return ActionError(
                message=(
                    f"The agent's answer was too large to return (over {MAX_EVENT_BYTES // (1024 * 1024)} MB). "
                    "Ask for a narrower result, e.g. the top N rows."
                )
            )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            # The run may already be executing server-side, so it is not retried.
            return ActionError(
                message=(
                    "The agent run did not finish: the connection was lost or it exceeded the time limit. "
                    "Try a narrower question."
                )
            )

        return ActionResult(data={"response": content or "No response from agent."})


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
