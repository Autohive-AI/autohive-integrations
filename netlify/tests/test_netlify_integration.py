"""
End-to-end integration tests for the Netlify integration.

These tests call the real Netlify API and require a valid personal access token
set in the NETLIFY_ACCESS_TOKEN environment variable.

Run all read-only tests:
    pytest netlify/tests/test_netlify_integration.py -m "integration and not destructive"

Run destructive tests (sites / deploys created on the real account):
    pytest netlify/tests/test_netlify_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from unittest.mock import AsyncMock, MagicMock

import netlify as netlify_mod  # noqa: E402

netlify_integration = netlify_mod.netlify

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("NETLIFY_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("NETLIFY_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, data=None, **kwargs):
        auth_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        merged_headers = {**auth_headers, **(headers or {})}
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                headers=merged_headers,
                data=data,
            ) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                if not resp.ok:
                    raise HTTPError(resp.status, str(resp_data))
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# =============================================================================
# LIST SITES
# =============================================================================


class TestListSites:
    async def test_returns_list(self, live_context):
        result = await netlify_integration.execute_action("list_sites", {}, live_context)
        data = result.result.data
        assert "sites" in data
        assert isinstance(data["sites"], list)

    async def test_site_items_have_id_and_name(self, live_context):
        result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")
        site = sites[0]
        assert "id" in site
        assert "name" in site


# =============================================================================
# GET SITE
# =============================================================================


class TestGetSite:
    async def test_returns_site_details(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        result = await netlify_integration.execute_action("get_site", {"site_id": site_id}, live_context)
        data = result.result.data
        assert "site" in data
        assert data["site"]["id"] == site_id

    async def test_site_has_expected_fields(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        result = await netlify_integration.execute_action("get_site", {"site_id": site_id}, live_context)
        site = result.result.data["site"]
        assert "id" in site
        assert "name" in site
        assert "url" in site or "ssl_url" in site


# =============================================================================
# LIST DEPLOYS
# =============================================================================


class TestListDeploys:
    async def test_returns_deploys_list(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        result = await netlify_integration.execute_action("list_deploys", {"site_id": site_id}, live_context)
        data = result.result.data
        assert "deploys" in data
        assert isinstance(data["deploys"], list)

    async def test_deploy_items_have_id_and_state(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        result = await netlify_integration.execute_action("list_deploys", {"site_id": site_id}, live_context)
        deploys = result.result.data["deploys"]
        if not deploys:
            pytest.skip("No deploys on this site")
        deploy = deploys[0]
        assert "id" in deploy
        assert "state" in deploy


# =============================================================================
# GET DEPLOY
# =============================================================================


class TestGetDeploy:
    async def test_returns_deploy_details(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        deploys_result = await netlify_integration.execute_action("list_deploys", {"site_id": site_id}, live_context)
        deploys = deploys_result.result.data["deploys"]
        if not deploys:
            pytest.skip("No deploys on this site")

        deploy_id = deploys[0]["id"]
        result = await netlify_integration.execute_action("get_deploy", {"deploy_id": deploy_id}, live_context)
        data = result.result.data
        assert "deploy" in data
        assert data["deploy"]["id"] == deploy_id

    async def test_deploy_has_state_field(self, live_context):
        list_result = await netlify_integration.execute_action("list_sites", {}, live_context)
        sites = list_result.result.data["sites"]
        if not sites:
            pytest.skip("No sites on this account")

        site_id = sites[0]["id"]
        deploys_result = await netlify_integration.execute_action("list_deploys", {"site_id": site_id}, live_context)
        deploys = deploys_result.result.data["deploys"]
        if not deploys:
            pytest.skip("No deploys on this site")

        deploy_id = deploys[0]["id"]
        result = await netlify_integration.execute_action("get_deploy", {"deploy_id": deploy_id}, live_context)
        assert "state" in result.result.data["deploy"]


# =============================================================================
# DESTRUCTIVE — create/update/delete site and deploy (writes to real account)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestSiteLifecycle:
    """Create site → update it → delete it.

    Uses a unique test name to avoid collisions. Cleans up even on failure
    via the site_id tracking pattern.
    """

    async def test_full_lifecycle(self, live_context):
        import time

        test_name = f"autohive-test-{int(time.time())}"
        site_id = None

        try:
            # Create
            create_result = await netlify_integration.execute_action("create_site", {"name": test_name}, live_context)
            assert "site" in create_result.result.data
            site_id = create_result.result.data["site"]["id"]
            assert site_id

            # Get — verify it exists
            get_result = await netlify_integration.execute_action("get_site", {"site_id": site_id}, live_context)
            assert get_result.result.data["site"]["id"] == site_id

            # Update name
            new_name = f"{test_name}-updated"
            update_result = await netlify_integration.execute_action(
                "update_site", {"site_id": site_id, "name": new_name}, live_context
            )
            assert "site" in update_result.result.data

        finally:
            if site_id:
                delete_result = await netlify_integration.execute_action(
                    "delete_site", {"site_id": site_id}, live_context
                )
                assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
class TestDeployLifecycle:
    """Create a site, deploy a file to it, then clean up.

    This tests the full create_deploy flow including file hashing and
    (potentially) file upload when Netlify requests the content.
    """

    async def test_create_deploy_and_verify(self, live_context):
        import time

        site_name = f"autohive-deploy-test-{int(time.time())}"
        site_id = None

        try:
            # Create a site to deploy to
            create_site_result = await netlify_integration.execute_action(
                "create_site", {"name": site_name}, live_context
            )
            site_id = create_site_result.result.data["site"]["id"]
            assert site_id

            # Deploy a simple HTML file
            deploy_result = await netlify_integration.execute_action(
                "create_deploy",
                {
                    "site_id": site_id,
                    "files": {"/index.html": "<html><body><h1>Autohive Integration Test</h1></body></html>"},
                },
                live_context,
            )
            data = deploy_result.result.data
            assert "deploy" in data
            assert "deploy_url" in data
            assert data["deploy"]["id"]

        finally:
            if site_id:
                await netlify_integration.execute_action("delete_site", {"site_id": site_id}, live_context)
