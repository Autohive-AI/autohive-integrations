"""
Unit tests for the Netlify integration using mocked fetch (SDK 2.0.0).

Covers every action: list_sites, create_site, get_site, update_site,
delete_site, list_deploys, create_deploy, get_deploy.

Each action is tested for: happy path, key request details (URL + method),
error path (ActionError), and important edge cases (list coercion, multi-fetch
sequencing, deploy_url priority, missing required inputs).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

import netlify as netlify_mod  # noqa: E402

netlify_integration = netlify_mod.netlify

pytestmark = pytest.mark.unit


def ok(data, status=200):
    """Wrap data in a successful FetchResponse."""
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    """Mock context with a single fetch response."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {}
    return ctx


def make_ctx_multi(responses: list):
    """Mock context with sequential fetch responses."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {}
    return ctx


def make_ctx_error(exc: Exception):
    """Mock context whose fetch raises an exception."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc)
    ctx.auth = {}
    return ctx


# =============================================================================
# LIST SITES
# =============================================================================


@pytest.mark.asyncio
async def test_list_sites_returns_sites():
    sites = [{"id": "site1", "name": "my-site"}, {"id": "site2", "name": "other-site"}]
    ctx = make_ctx(sites)
    result = await netlify_integration.execute_action("list_sites", {}, ctx)
    assert result.result.data["sites"] == sites


@pytest.mark.asyncio
async def test_list_sites_non_list_response_coerces_to_empty():
    ctx = make_ctx({"error": "unexpected"})
    result = await netlify_integration.execute_action("list_sites", {}, ctx)
    assert result.result.data["sites"] == []


@pytest.mark.asyncio
async def test_list_sites_empty_list():
    ctx = make_ctx([])
    result = await netlify_integration.execute_action("list_sites", {}, ctx)
    assert result.result.data["sites"] == []


@pytest.mark.asyncio
async def test_list_sites_calls_correct_url():
    ctx = make_ctx([])
    await netlify_integration.execute_action("list_sites", {}, ctx)
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/sites")
    assert ctx.fetch.call_args.kwargs.get("method") == "GET"


@pytest.mark.asyncio
async def test_list_sites_error_returns_action_error():
    ctx = make_ctx_error(Exception("Network failure"))
    result = await netlify_integration.execute_action("list_sites", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Network failure" in result.result.message


# =============================================================================
# CREATE SITE
# =============================================================================


@pytest.mark.asyncio
async def test_create_site_returns_site():
    site = {"id": "new-site-id", "name": "test-site", "url": "https://test-site.netlify.app"}
    ctx = make_ctx(site)
    result = await netlify_integration.execute_action("create_site", {"name": "test-site"}, ctx)
    assert result.result.data["site"] == site


@pytest.mark.asyncio
async def test_create_site_sends_name_in_payload():
    ctx = make_ctx({"id": "s1", "name": "my-site"})
    await netlify_integration.execute_action("create_site", {"name": "my-site"}, ctx)
    assert ctx.fetch.call_args.kwargs.get("method") == "POST"
    assert ctx.fetch.call_args.kwargs.get("json", {}).get("name") == "my-site"


@pytest.mark.asyncio
async def test_create_site_includes_custom_domain_when_provided():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("create_site", {"name": "my-site", "custom_domain": "example.com"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload.get("custom_domain") == "example.com"


@pytest.mark.asyncio
async def test_create_site_omits_custom_domain_when_absent():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("create_site", {"name": "my-site"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert "custom_domain" not in payload


@pytest.mark.asyncio
async def test_create_site_missing_name_returns_validation_error():
    ctx = make_ctx({})
    result = await netlify_integration.execute_action("create_site", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_site_error_returns_action_error():
    ctx = make_ctx_error(Exception("API error"))
    result = await netlify_integration.execute_action("create_site", {"name": "my-site"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "API error" in result.result.message


# =============================================================================
# GET SITE
# =============================================================================


@pytest.mark.asyncio
async def test_get_site_returns_site_details():
    site = {"id": "site-abc", "name": "my-site", "url": "https://my-site.netlify.app"}
    ctx = make_ctx(site)
    result = await netlify_integration.execute_action("get_site", {"site_id": "site-abc"}, ctx)
    assert result.result.data["site"] == site


@pytest.mark.asyncio
async def test_get_site_calls_site_id_url():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("get_site", {"site_id": "site-abc"}, ctx)
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert "site-abc" in url
    assert ctx.fetch.call_args.kwargs.get("method") == "GET"


@pytest.mark.asyncio
async def test_get_site_missing_site_id_returns_validation_error():
    ctx = make_ctx({})
    result = await netlify_integration.execute_action("get_site", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_site_error_returns_action_error():
    ctx = make_ctx_error(Exception("Not found"))
    result = await netlify_integration.execute_action("get_site", {"site_id": "bad-id"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Not found" in result.result.message


# =============================================================================
# UPDATE SITE
# =============================================================================


@pytest.mark.asyncio
async def test_update_site_returns_updated_site():
    site = {"id": "s1", "name": "new-name"}
    ctx = make_ctx(site)
    result = await netlify_integration.execute_action("update_site", {"site_id": "s1", "name": "new-name"}, ctx)
    assert result.result.data["site"] == site


@pytest.mark.asyncio
async def test_update_site_sends_patch_to_site_url():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("update_site", {"site_id": "s1", "name": "renamed"}, ctx)
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert "s1" in url
    assert ctx.fetch.call_args.kwargs.get("method") == "PATCH"


@pytest.mark.asyncio
async def test_update_site_sends_name_in_payload():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("update_site", {"site_id": "s1", "name": "renamed"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload.get("name") == "renamed"


@pytest.mark.asyncio
async def test_update_site_sends_custom_domain_in_payload():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("update_site", {"site_id": "s1", "custom_domain": "new.example.com"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload.get("custom_domain") == "new.example.com"


@pytest.mark.asyncio
async def test_update_site_omits_empty_optional_fields():
    ctx = make_ctx({"id": "s1"})
    await netlify_integration.execute_action("update_site", {"site_id": "s1"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert "name" not in payload
    assert "custom_domain" not in payload


@pytest.mark.asyncio
async def test_update_site_error_returns_action_error():
    ctx = make_ctx_error(Exception("Forbidden"))
    result = await netlify_integration.execute_action("update_site", {"site_id": "s1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Forbidden" in result.result.message


# =============================================================================
# DELETE SITE
# =============================================================================


@pytest.mark.asyncio
async def test_delete_site_returns_deleted_true():
    ctx = make_ctx(None)
    result = await netlify_integration.execute_action("delete_site", {"site_id": "s1"}, ctx)
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_delete_site_sends_delete_method():
    ctx = make_ctx(None)
    await netlify_integration.execute_action("delete_site", {"site_id": "site-del"}, ctx)
    assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert "site-del" in url


@pytest.mark.asyncio
async def test_delete_site_missing_site_id_returns_validation_error():
    ctx = make_ctx(None)
    result = await netlify_integration.execute_action("delete_site", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_delete_site_error_returns_action_error():
    ctx = make_ctx_error(Exception("Not found"))
    result = await netlify_integration.execute_action("delete_site", {"site_id": "gone"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Not found" in result.result.message


# =============================================================================
# LIST DEPLOYS
# =============================================================================


@pytest.mark.asyncio
async def test_list_deploys_returns_deploys():
    deploys = [{"id": "d1", "state": "ready"}, {"id": "d2", "state": "building"}]
    ctx = make_ctx(deploys)
    result = await netlify_integration.execute_action("list_deploys", {"site_id": "s1"}, ctx)
    assert result.result.data["deploys"] == deploys


@pytest.mark.asyncio
async def test_list_deploys_non_list_response_coerces_to_empty():
    ctx = make_ctx({"unexpected": "dict"})
    result = await netlify_integration.execute_action("list_deploys", {"site_id": "s1"}, ctx)
    assert result.result.data["deploys"] == []


@pytest.mark.asyncio
async def test_list_deploys_calls_site_deploys_url():
    ctx = make_ctx([])
    await netlify_integration.execute_action("list_deploys", {"site_id": "site-xyz"}, ctx)
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert "site-xyz" in url
    assert url.endswith("/deploys")
    assert ctx.fetch.call_args.kwargs.get("method") == "GET"


@pytest.mark.asyncio
async def test_list_deploys_error_returns_action_error():
    ctx = make_ctx_error(Exception("Timeout"))
    result = await netlify_integration.execute_action("list_deploys", {"site_id": "s1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Timeout" in result.result.message


# =============================================================================
# CREATE DEPLOY
# =============================================================================


@pytest.mark.asyncio
async def test_create_deploy_no_required_files():
    """When Netlify returns no required hashes, no file uploads happen."""
    deploy_init = {"id": "deploy-1", "required": []}
    final_deploy = {"id": "deploy-1", "state": "ready", "deploy_ssl_url": "https://deploy-1.netlify.app"}
    ctx = make_ctx_multi([deploy_init, final_deploy])

    result = await netlify_integration.execute_action(
        "create_deploy",
        {"site_id": "s1", "files": {"/index.html": "<html>Hello</html>"}},
        ctx,
    )
    data = result.result.data
    assert data["deploy"]["id"] == "deploy-1"
    assert data["deploy_url"] == "https://deploy-1.netlify.app"
    assert ctx.fetch.call_count == 2


@pytest.mark.asyncio
async def test_create_deploy_uploads_required_files():
    """When required hashes are returned, the matching file content is uploaded."""
    content = "<html>Hello</html>"
    import hashlib

    sha1 = hashlib.sha1(content.encode(), usedforsecurity=False).hexdigest()

    deploy_init = {"id": "deploy-2", "required": [sha1]}
    final_deploy = {"id": "deploy-2", "state": "ready", "ssl_url": "https://deploy-2.netlify.app"}
    # 3 calls: create deploy, upload file, get final deploy
    ctx = make_ctx_multi([deploy_init, None, final_deploy])

    await netlify_integration.execute_action(
        "create_deploy",
        {"site_id": "s1", "files": {"/index.html": content}},
        ctx,
    )
    assert ctx.fetch.call_count == 3
    # second call is the file upload (PUT)
    upload_call = ctx.fetch.call_args_list[1]
    upload_url = upload_call.args[0] if upload_call.args else upload_call.kwargs.get("url", "")
    assert upload_call.kwargs.get("method") == "PUT"
    assert "deploy-2" in upload_url
    assert "/index.html" in upload_url
    assert upload_call.kwargs.get("headers", {}).get("Content-Type") == "application/octet-stream"


@pytest.mark.asyncio
async def test_create_deploy_url_priority_ssl_url_over_url():
    """deploy_ssl_url is preferred over ssl_url, which is preferred over url."""
    deploy_init = {"id": "d1", "required": []}
    final_deploy = {
        "id": "d1",
        "deploy_ssl_url": "https://deploy-ssl.netlify.app",
        "ssl_url": "https://ssl.netlify.app",
        "url": "https://plain.netlify.app",
    }
    ctx = make_ctx_multi([deploy_init, final_deploy])
    result = await netlify_integration.execute_action(
        "create_deploy", {"site_id": "s1", "files": {"/index.html": "hi"}}, ctx
    )
    assert result.result.data["deploy_url"] == "https://deploy-ssl.netlify.app"


@pytest.mark.asyncio
async def test_create_deploy_url_fallback_to_ssl_url():
    deploy_init = {"id": "d1", "required": []}
    final_deploy = {"id": "d1", "ssl_url": "https://ssl.netlify.app", "url": "https://plain.netlify.app"}
    ctx = make_ctx_multi([deploy_init, final_deploy])
    result = await netlify_integration.execute_action(
        "create_deploy", {"site_id": "s1", "files": {"/index.html": "hi"}}, ctx
    )
    assert result.result.data["deploy_url"] == "https://ssl.netlify.app"


@pytest.mark.asyncio
async def test_create_deploy_url_fallback_to_url():
    deploy_init = {"id": "d1", "required": []}
    final_deploy = {"id": "d1", "url": "https://plain.netlify.app"}
    ctx = make_ctx_multi([deploy_init, final_deploy])
    result = await netlify_integration.execute_action(
        "create_deploy", {"site_id": "s1", "files": {"/index.html": "hi"}}, ctx
    )
    assert result.result.data["deploy_url"] == "https://plain.netlify.app"


@pytest.mark.asyncio
async def test_create_deploy_multiple_files_hashed_correctly():
    """Each file in the mapping gets its own SHA1 digest in the payload."""
    import hashlib

    files = {"/index.html": "<html>A</html>", "/style.css": "body { color: red; }"}
    expected_hashes = {
        path: hashlib.sha1(content.encode(), usedforsecurity=False).hexdigest() for path, content in files.items()
    }

    deploy_init = {"id": "d1", "required": []}
    final_deploy = {"id": "d1", "deploy_ssl_url": "https://d1.netlify.app"}
    ctx = make_ctx_multi([deploy_init, final_deploy])

    await netlify_integration.execute_action("create_deploy", {"site_id": "s1", "files": files}, ctx)

    sent_files = ctx.fetch.call_args_list[0].kwargs.get("json", {}).get("files", {})
    for path, sha1 in expected_hashes.items():
        assert sent_files[path] == sha1


@pytest.mark.asyncio
async def test_create_deploy_missing_id_in_deploy_response_returns_action_error():
    """If Netlify's initial create-deploy response has no 'id', ActionError before any URL corruption."""
    deploy_init = {"required": ["abc123"]}  # no "id" key
    ctx = make_ctx(deploy_init)
    result = await netlify_integration.execute_action(
        "create_deploy",
        {"site_id": "s1", "files": {"/index.html": "hi"}},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "deploy ID" in result.result.message


@pytest.mark.asyncio
async def test_create_deploy_error_returns_action_error():
    ctx = make_ctx_error(Exception("Deploy failed"))
    result = await netlify_integration.execute_action(
        "create_deploy", {"site_id": "s1", "files": {"/index.html": "hi"}}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Deploy failed" in result.result.message


@pytest.mark.asyncio
async def test_create_deploy_missing_required_inputs_returns_validation_error():
    ctx = make_ctx({})
    result = await netlify_integration.execute_action("create_deploy", {"site_id": "s1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# GET DEPLOY
# =============================================================================


@pytest.mark.asyncio
async def test_get_deploy_returns_deploy_details():
    deploy = {"id": "d1", "state": "ready", "deploy_ssl_url": "https://d1.netlify.app"}
    ctx = make_ctx(deploy)
    result = await netlify_integration.execute_action("get_deploy", {"deploy_id": "d1"}, ctx)
    assert result.result.data["deploy"] == deploy


@pytest.mark.asyncio
async def test_get_deploy_calls_deploy_url():
    ctx = make_ctx({"id": "d99"})
    await netlify_integration.execute_action("get_deploy", {"deploy_id": "d99"}, ctx)
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert "d99" in url
    assert ctx.fetch.call_args.kwargs.get("method") == "GET"


@pytest.mark.asyncio
async def test_get_deploy_missing_deploy_id_returns_validation_error():
    ctx = make_ctx({})
    result = await netlify_integration.execute_action("get_deploy", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_deploy_error_returns_action_error():
    ctx = make_ctx_error(Exception("Deploy not found"))
    result = await netlify_integration.execute_action("get_deploy", {"deploy_id": "bad-id"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Deploy not found" in result.result.message
