from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any
from urllib.parse import quote
import hashlib

# Create the integration
netlify = Integration.load()

# Base URL for Netlify API
NETLIFY_API_BASE_URL = "https://api.netlify.com/api/v1"

# Netlify's API guide is explicit: "Be sure to escape the file_path parameter,
# and ensure file paths don't include # or ? characters." A path is used two
# different ways, and conflating them is what makes this subtle:
#
#   * as a *logical* key in the deploy's file digest ("/index.html"), unescaped
#   * as part of the *upload URL* (PUT /deploys/{id}/files/index.html), escaped
#
# Anything the URL parser treats specially therefore has to be rejected or
# encoded, or the two disagree and the upload silently targets the wrong path.
FORBIDDEN_PATH_CHARACTERS = {
    "#": "fragment delimiter",
    "?": "query delimiter",
    "\\": "backslash",
}


def normalize_deploy_path(path: Any) -> str:
    """Validate a caller-supplied deploy path and return its logical form.

    The result always has exactly one leading slash and no dot segments, so it
    is safe to use as a digest key and, once escaped, as an upload URL.

    Raises ValueError for anything that could not round-trip: an empty path, a
    character the URL parser would treat as a delimiter, or a component that
    URL normalization would rewrite. Dot segments matter most here: an upload
    URL containing "/../" is normalized by the HTTP client before it is sent,
    so "assets/../index.html" would be declared under that literal digest key
    but uploaded to "/files/index.html", and "../secret.txt" would resolve
    outside the /files endpoint entirely.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Deploy file paths cannot be empty.")

    for character, description in FORBIDDEN_PATH_CHARACTERS.items():
        if character in path:
            raise ValueError(
                f"Deploy file path '{path}' contains '{character}' ({description}), "
                "which Netlify does not allow in deploy paths."
            )

    components = path.lstrip("/").split("/")
    if not any(components):
        raise ValueError("Deploy file paths cannot be empty.")

    for component in components:
        if component == "":
            raise ValueError(f"Deploy file path '{path}' has an empty path segment (consecutive slashes).")
        if component in (".", ".."):
            raise ValueError(
                f"Deploy file path '{path}' contains a '{component}' segment. "
                "Relative segments are rewritten by URL normalization, so the uploaded "
                "file would not land at the declared path."
            )

    return "/" + "/".join(components)


def encode_deploy_path(logical_path: str) -> str:
    """Percent-encode a normalized path for use in the upload URL.

    Each component is escaped separately so that the "/" separators survive,
    while spaces, non-ASCII characters and literal "%" are encoded. The digest
    key keeps the unescaped logical form; only the URL is escaped.
    """
    return "/" + "/".join(quote(component, safe="") for component in logical_path.lstrip("/").split("/"))


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
        # Tracks which request is in flight so a failure names the step that broke.
        step = "preparing file digests"
        try:
            site_id = inputs["site_id"]
            files = inputs["files"]

            # Prepare files dictionary with SHA1 hashes
            files_dict = {}
            hash_to_content = {}
            hash_to_path = {}

            # Every path is validated before the deploy is created, so an invalid
            # path fails without leaving a half-built deploy behind.
            for path, content in files.items():
                # Netlify keys the "required" list off the paths declared here, and
                # its upload route is /files/<path>. Both sides use this logical
                # form, so "index.html" and "/index.html" are treated identically.
                normalized_path = normalize_deploy_path(path)
                sha1 = hashlib.sha1(content.encode(), usedforsecurity=False).hexdigest()  # nosec B324

                files_dict[normalized_path] = sha1
                if sha1 not in hash_to_content:
                    hash_to_content[sha1] = content
                    hash_to_path[sha1] = normalized_path

            # Create deploy with file digests
            step = f"creating deploy for site {site_id}"
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

                    # The digest key stays unescaped; only the URL is escaped.
                    step = f"uploading {file_path} to deploy {deploy_id}"
                    await context.fetch(
                        f"{NETLIFY_API_BASE_URL}/deploys/{deploy_id}/files{encode_deploy_path(file_path)}",
                        method="PUT",
                        headers={"Content-Type": "application/octet-stream"},
                        data=file_content.encode(),
                    )

            # Get final deploy info
            step = f"retrieving deploy {deploy_id}"
            final_response = await context.fetch(f"{NETLIFY_API_BASE_URL}/deploys/{deploy_id}", method="GET")
            final_deploy = final_response.data

            deploy_url = (
                final_deploy.get("deploy_ssl_url") or final_deploy.get("ssl_url") or final_deploy.get("url", "")
            )

            return ActionResult(data={"deploy": final_deploy, "deploy_url": deploy_url}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=f"{e} (while {step})")


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
