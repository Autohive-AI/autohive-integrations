from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any
import hashlib

# Create the integration
netlify = Integration.load()

# Base URL for Netlify API
NETLIFY_API_BASE_URL = "https://api.netlify.com/api/v1"

# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


# ---- Site Handlers ----


@netlify.action("list_sites")
class ListSitesAction(ActionHandler):
    """List all sites for the authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/sites", method="GET")

            sites = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"sites": sites}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("create_site")
class CreateSiteAction(ActionHandler):
    """Create a new site."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            name = inputs["name"]

            payload = {"name": name}

            if inputs.get("custom_domain"):
                payload["custom_domain"] = inputs["custom_domain"]

            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/sites", method="POST", json=payload)

            return ActionResult(data={"site": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("get_site")
class GetSiteAction(ActionHandler):
    """Get details of a specific site."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            site_id = inputs["site_id"]

            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/sites/{site_id}", method="GET")

            return ActionResult(data={"site": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("update_site")
class UpdateSiteAction(ActionHandler):
    """Update site settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            site_id = inputs["site_id"]

            payload = {}
            if inputs.get("name"):
                payload["name"] = inputs["name"]
            if inputs.get("custom_domain"):
                payload["custom_domain"] = inputs["custom_domain"]

            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/sites/{site_id}", method="PATCH", json=payload)

            return ActionResult(data={"site": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("delete_site")
class DeleteSiteAction(ActionHandler):
    """Delete a site."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            site_id = inputs["site_id"]

            await context.fetch(f"{NETLIFY_API_BASE_URL}/sites/{site_id}", method="DELETE")

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Deploy Handlers ----


@netlify.action("list_deploys")
class ListDeploysAction(ActionHandler):
    """List all deploys for a site."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            site_id = inputs["site_id"]

            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/sites/{site_id}/deploys", method="GET")

            deploys = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"deploys": deploys}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("create_deploy")
class CreateDeployAction(ActionHandler):
    """Create a new deploy for a site with files."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            site_id = inputs["site_id"]
            files = inputs["files"]

            # Prepare files dictionary with SHA1 hashes
            files_dict = {}
            hash_to_content = {}
            hash_to_path = {}

            for path, content in files.items():
                sha1 = hashlib.sha1(content.encode(), usedforsecurity=False).hexdigest()  # nosec B324
                files_dict[path] = sha1
                if sha1 not in hash_to_content:
                    hash_to_content[sha1] = content
                    hash_to_path[sha1] = path

            # Create deploy with file digests
            deploy_response = await context.fetch(
                f"{NETLIFY_API_BASE_URL}/sites/{site_id}/deploys", method="POST", json={"files": files_dict}
            )
            deploy = deploy_response.data

            # Upload required files
            required_hashes = deploy.get("required", [])
            deploy_id = deploy.get("id")
            if not deploy_id:
                raise ValueError("Netlify did not return a deploy ID — cannot upload files or retrieve deploy status")

            for sha1_hash in required_hashes:
                if sha1_hash in hash_to_content:
                    file_content = hash_to_content[sha1_hash]
                    file_path = hash_to_path[sha1_hash]

                    await context.fetch(
                        f"{NETLIFY_API_BASE_URL}/deploys/{deploy_id}/files{file_path}",
                        method="PUT",
                        headers={"Content-Type": "application/octet-stream"},
                        data=file_content.encode(),
                    )

            # Get final deploy info
            final_response = await context.fetch(f"{NETLIFY_API_BASE_URL}/deploys/{deploy_id}", method="GET")
            final_deploy = final_response.data

            deploy_url = (
                final_deploy.get("deploy_ssl_url") or final_deploy.get("ssl_url") or final_deploy.get("url", "")
            )

            return ActionResult(data={"deploy": final_deploy, "deploy_url": deploy_url}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@netlify.action("get_deploy")
class GetDeployAction(ActionHandler):
    """Get details of a specific deploy."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deploy_id = inputs["deploy_id"]

            response = await context.fetch(f"{NETLIFY_API_BASE_URL}/deploys/{deploy_id}", method="GET")

            return ActionResult(data={"deploy": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
