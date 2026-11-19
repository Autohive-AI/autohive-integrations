"""Live Figma API tests. See README for fixture setup and safe/destructive commands.

All HTTP responses come from Figma; no response payloads are mocked. The
context adapter supplies the SDK platform OAuth Bearer header, or uses
X-Figma-Token for the documented local-only personal access token fallback.
"""

import asyncio
import json as jsonlib
import os
import time
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from figma.figma import figma

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def read_cache():
    """Reuse identical reads within one run to respect Figma's plan-dependent limits."""
    return {}


@pytest.fixture(scope="module")
def api_budget():
    return {"last_design_read": 0.0}


@pytest.fixture
def fixture_value(env_credentials):
    def require(name):
        value = env_credentials(name)
        if not value:
            pytest.skip(f"{name} not configured for the dedicated Figma test account")
        return value

    return require


@pytest.fixture
async def live_context(fixture_value, env_credentials, request, api_budget):
    oauth_token = env_credentials("FIGMA_ACCESS_TOKEN")
    personal_token = env_credentials("FIGMA_PERSONAL_ACCESS_TOKEN")
    token = oauth_token or personal_token
    if not token:
        pytest.skip("Configure FIGMA_ACCESS_TOKEN or a local FIGMA_PERSONAL_ACCESS_TOKEN for live API tests")
    token_header = "Authorization" if oauth_token else "X-Figma-Token"
    token_value = f"Bearer {token}" if oauth_token else token
    created_comments = []
    allow_writes = (
        request.node.get_closest_marker("destructive") is not None
        and env_credentials("FIGMA_RUN_DESTRUCTIVE_TESTS") == "1"
    )
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:

        async def real_fetch(url, *, method="GET", headers=None, params=None, json=None):
            parsed = urlparse(url)
            assert parsed.scheme == "https" and parsed.netloc == "api.figma.com"
            if method != "GET":
                assert allow_writes, "Writes require a destructive test and FIGMA_RUN_DESTRUCTIVE_TESTS=1"
            # File/node reads and renders share Figma's restrictive Tier 1 budget.
            # Space uncached design requests below ten/minute across the whole suite.
            segments = parsed.path.strip("/").split("/")
            design_read = method == "GET" and (
                segments[:2] == ["v1", "images"]
                or (segments[:2] == ["v1", "files"] and (len(segments) == 3 or segments[-1] == "nodes"))
            )
            if design_read:
                delay = 7 - (time.monotonic() - api_budget["last_design_read"])
                if delay > 0:
                    await asyncio.sleep(delay)
                api_budget["last_design_read"] = time.monotonic()
            merged_headers = {**(headers or {}), token_header: token_value}
            async with session.request(method, url, headers=merged_headers, params=params, json=json) as response:
                text = await response.text()
                data = jsonlib.loads(text) if text else None
                if method == "GET" and len(segments) == 4 and segments[-1] == "images":
                    context.image_fill_response_shape = (
                        "images" if isinstance(data, dict) and "images" in data else "meta.images"
                    )
                # Register successful writes before SDK output validation or test assertions.
                # This lets teardown clean up even if an assertion later fails.
                if method == "POST" and response.status < 300 and isinstance(data, dict) and data.get("id"):
                    created_comments.append((parsed.path.split("/")[3], data["id"]))
                if method == "DELETE" and response.status < 300:
                    deleted = (parsed.path.split("/")[3], parsed.path.split("/")[-1])
                    if deleted in created_comments:
                        created_comments.remove(deleted)
                return FetchResponse(status=response.status, headers=dict(response.headers), data=data)

        context = MagicMock(name="ExecutionContext")
        context.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
        context.fetch = AsyncMock(side_effect=real_fetch)
        try:
            yield context
        finally:
            failures = []
            for file_key, comment_id in reversed(created_comments.copy()):
                try:
                    result = await figma.execute_action(
                        "delete_comment", {"file_key": file_key, "comment_id": comment_id}, context
                    )
                    if result.type != ResultType.ACTION:
                        failures.append(comment_id)
                except Exception:
                    # Attempt every cleanup even when one request fails; never hide leftovers.
                    failures.append(comment_id)
            assert not failures, f"Could not clean up Figma test comment IDs: {failures}"


@pytest.fixture
def call(live_context, read_cache):
    async def invoke(action, inputs, *, fresh=False):
        key = (action, jsonlib.dumps(inputs, sort_keys=True))
        is_read = action not in {"create_comment", "delete_comment"}
        if is_read and not fresh and key in read_cache:
            return read_cache[key]
        result = await figma.execute_action(action, inputs, live_context)
        assert result.type == ResultType.ACTION, f"{action} failed: {getattr(result.result, 'message', result.type)}"
        data = result.result.data
        assert isinstance(data, dict)
        if is_read and not fresh:
            read_cache[key] = data
        return data

    return invoke


@pytest.fixture
def file_key(fixture_value):
    return fixture_value("FIGMA_TEST_FILE_KEY")


@pytest.fixture
def node_id(fixture_value):
    return fixture_value("FIGMA_TEST_NODE_ID")


@pytest.fixture
def team_id(fixture_value):
    return fixture_value("FIGMA_TEST_TEAM_ID")


def assert_asset(asset):
    assert isinstance(asset, dict)
    assert isinstance(asset.get("key"), str) and asset["key"]
    assert isinstance(asset.get("name"), str) and asset["name"]
    assert isinstance(asset.get("node_id"), str) and asset["node_id"]


def version_cursor(link, file_key):
    """Extract the cursor, never issue a request to an arbitrary pagination URL."""
    parsed = urlparse(link)
    assert parsed.scheme == "https" and parsed.netloc == "api.figma.com"
    assert parsed.path == f"/v1/files/{file_key}/versions"
    query = parse_qs(parsed.query)
    names = [name for name in ("before", "after") if name in query]
    assert len(names) == 1, "Expected exactly one version pagination cursor"
    return {names[0]: int(query[names[0]][0])}


class TestAccount:
    async def test_user_identity(self, call):
        data = await call("get_me", {})
        assert data["id"] and data["handle"]
        assert "@" in data["email"]


class TestFiles:
    async def test_document_tree(self, call, file_key):
        data = await call("get_file", {"file_key": file_key, "depth": 2})
        assert data["name"] and data["version"]
        assert data["document"]["type"] == "DOCUMENT"
        assert data["document"]["children"], "Seed a page with a renderable node"
        assert all(page["type"] == "CANVAS" for page in data["document"]["children"])

    async def test_metadata_matches_document(self, call, file_key):
        metadata = (await call("get_file_metadata", {"file_key": file_key}))["file"]
        document = await call("get_file", {"file_key": file_key, "depth": 2})
        assert metadata["name"] == document["name"]
        assert metadata["creator"]["id"]
        assert metadata["last_touched_at"]
        assert metadata["editorType"] == "figma"

    async def test_requested_node_round_trip(self, call, file_key, node_id):
        data = await call("get_file_nodes", {"file_key": file_key, "ids": [node_id], "depth": 2})
        node = data["nodes"][node_id]["document"]
        assert node["id"] == node_id
        assert node["name"] and node["type"]

    async def test_missing_node_is_returned_as_null(self, call, file_key):
        missing_id = "999999999:999999999"
        data = await call("get_file_nodes", {"file_key": file_key, "ids": [missing_id]})
        assert missing_id in data["nodes"]
        assert data["nodes"][missing_id] is None

    async def test_file_node_filter_matches_node_endpoint(self, call, file_key, node_id):
        filtered = await call("get_file", {"file_key": file_key, "ids": [node_id]})
        selected = await call("get_file_nodes", {"file_key": file_key, "ids": [node_id], "depth": 2})
        pending = [filtered["document"]]
        found = None
        while pending:
            node = pending.pop()
            if node["id"] == node_id:
                found = node
                break
            pending.extend(node.get("children", []))
        assert found is not None
        assert found["type"] == selected["nodes"][node_id]["document"]["type"]

    @pytest.mark.parametrize(
        "format,media_type,signature",
        [
            ("png", "image/png", b"\x89PNG\r\n\x1a\n"),
            ("jpg", "image/jpeg", b"\xff\xd8\xff"),
            ("pdf", "application/pdf", b"%PDF"),
            ("svg", "image/svg+xml", b"<svg"),
        ],
    )
    async def test_export_download_is_real_image(self, call, file_key, node_id, format, media_type, signature):
        data = await call("export_images", {"file_key": file_key, "ids": [node_id], "format": format, "scale": 1})
        url = data["images"][node_id]
        assert isinstance(url, str) and url.startswith("https://"), (
            "Use a small renderable frame for FIGMA_TEST_NODE_ID"
        )
        # Image hosts receive no OAuth header. Read only the prefix, not an unbounded download.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(url) as response:
                assert response.status == 200
                assert media_type in response.headers.get("Content-Type", "")
                prefix = await response.content.read(4096)
                assert prefix.startswith(signature) if format != "svg" else signature in prefix

    async def test_image_fills_have_downloadable_content(self, call, file_key, live_context, record_property):
        images = (await call("get_image_fills", {"file_key": file_key}))["images"]
        record_property("figma_image_fill_response_shape", live_context.image_fill_response_shape)
        assert images, "Seed an image fill in FIGMA_TEST_FILE_KEY"
        reference, url = next(iter(images.items()))
        assert reference and url.startswith("https://")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(url) as response:
                assert response.status == 200
                assert response.headers.get("Content-Type", "").startswith("image/")
                assert await response.content.read(32)

    async def test_missing_file_is_action_error(self, live_context):
        result = await figma.execute_action("get_file", {"file_key": uuid4().hex}, live_context)
        assert result.type == ResultType.ACTION_ERROR


class TestComments:
    async def test_nonempty_seeded_comments(self, call, file_key):
        comments = (await call("list_comments", {"file_key": file_key}))["comments"]
        assert comments, "Seed a permanent comment in the read-only fixture file"
        assert all(comment["id"] and comment["user"]["id"] for comment in comments)
        assert any(comment["message"] for comment in comments)

    async def test_markdown_keeps_comment_ids(self, call, file_key):
        plain = (await call("list_comments", {"file_key": file_key}))["comments"]
        markdown = (await call("list_comments", {"file_key": file_key, "as_md": True}))["comments"]
        assert plain and markdown
        assert {comment["id"] for comment in plain} == {comment["id"] for comment in markdown}
        assert all(isinstance(comment["message"], str) for comment in markdown)


class TestVersions:
    async def test_versions_have_identity_and_author(self, call, file_key):
        versions = (await call("list_file_versions", {"file_key": file_key, "page_size": 1}))["versions"]
        assert len(versions) == 1, "Seed at least two saved versions"
        assert versions[0]["id"] and versions[0]["created_at"] and versions[0]["user"]["id"]

    async def test_paginate_two_distinct_pages(self, call, file_key):
        first = await call("list_file_versions", {"file_key": file_key, "page_size": 1})
        link = first["pagination"].get("next_page")
        assert link, "Seed at least two saved file versions to exercise pagination"
        second = await call(
            "list_file_versions", {"file_key": file_key, "page_size": 1, **version_cursor(link, file_key)}
        )
        assert len(first["versions"]) == len(second["versions"]) == 1
        assert first["versions"][0]["id"] != second["versions"][0]["id"]

    async def test_historical_document_version(self, call, file_key):
        version = (await call("list_file_versions", {"file_key": file_key, "page_size": 1}))["versions"][0]["id"]
        data = await call("get_file", {"file_key": file_key, "version": version, "depth": 1})
        assert data["version"] == version
        assert data["document"]["type"] == "DOCUMENT"

    async def test_historical_node_identity(self, call, file_key, node_id):
        version = (await call("list_file_versions", {"file_key": file_key, "page_size": 1}))["versions"][0]["id"]
        data = await call("get_file_nodes", {"file_key": file_key, "ids": [node_id], "version": version})
        assert data["nodes"][node_id]["document"]["id"] == node_id


@pytest.mark.parametrize(
    "resource,singular",
    [
        ("components", "component"),
        ("component_sets", "component_set"),
        ("styles", "style"),
    ],
)
class TestPublishedLibraries:
    async def test_file_published_assets(self, call, file_key, resource, singular):
        assets = (await call(f"list_file_{resource}", {"file_key": file_key}))["meta"][resource]
        assert assets, f"Publish at least one {singular} in the fixture file"
        for asset in assets:
            assert_asset(asset)
            assert asset["file_key"] == file_key

    async def test_team_published_assets(self, call, team_id, resource, singular):
        assets = (await call(f"list_team_{resource}", {"team_id": team_id, "page_size": 1}))["meta"][resource]
        assert len(assets) == 1, f"Publish at least two team {resource} for the test account"
        assert_asset(assets[0])

    async def test_asset_key_round_trip(self, call, file_key, resource, singular):
        assets = (await call(f"list_file_{resource}", {"file_key": file_key}))["meta"][resource]
        assert assets, f"Publish at least one {singular} in the fixture file"
        asset = assets[0]
        detail = (await call(f"get_{singular}", {"key": asset["key"]}))["meta"]
        assert_asset(detail)
        assert detail["key"] == asset["key"]
        assert detail["file_key"] == file_key
        assert detail["node_id"] == asset["node_id"]
        assert detail["name"] == asset["name"]

    async def test_team_pagination_has_no_duplicate_assets(self, call, team_id, resource, singular):
        first = await call(f"list_team_{resource}", {"team_id": team_id, "page_size": 1})
        cursor = first["meta"].get("cursor", {}).get("after")
        assert cursor is not None, f"Publish at least two team {resource} to exercise pagination"
        second = await call(f"list_team_{resource}", {"team_id": team_id, "page_size": 1, "after": cursor})
        assert len(first["meta"][resource]) == len(second["meta"][resource]) == 1
        assert_asset(second["meta"][resource][0])
        assert first["meta"][resource][0]["key"] != second["meta"][resource][0]["key"]


@pytest.mark.destructive
class TestCommentLifecycle:
    async def test_create_reply_list_and_delete(self, env_credentials, fixture_value, live_context, call):
        if env_credentials("FIGMA_RUN_DESTRUCTIVE_TESTS") != "1":
            pytest.skip("Set FIGMA_RUN_DESTRUCTIVE_TESTS=1 only for a dedicated disposable comment fixture")
        file_key = fixture_value("FIGMA_TEST_COMMENT_FILE_KEY")
        marker = f"Autohive live test {os.getpid()} {uuid4().hex}"
        root = await call("create_comment", {"file_key": file_key, "message": marker})
        assert root["message"] == marker and root["id"]
        reply = await call(
            "create_comment", {"file_key": file_key, "message": marker + " reply", "comment_id": root["id"]}
        )
        assert reply["parent_id"] == root["id"]
        comments = (await call("list_comments", {"file_key": file_key}, fresh=True))["comments"]
        by_id = {comment["id"]: comment for comment in comments}
        assert by_id[root["id"]]["message"] == marker
        assert by_id[reply["id"]]["message"] == marker + " reply"
        for comment in (reply, root):
            assert (await call("delete_comment", {"file_key": file_key, "comment_id": comment["id"]}))["deleted"]
        remaining = (await call("list_comments", {"file_key": file_key}, fresh=True))["comments"]
        assert not {root["id"], reply["id"]} & {comment["id"] for comment in remaining}
