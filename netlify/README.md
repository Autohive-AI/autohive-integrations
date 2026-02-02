# Netlify Integration for Autohive

Connects Autohive to the Netlify API for managing sites, deployments, and hosting.

## Description

This integration provides a connection to Netlify's hosting platform. It allows users to manage sites, create and monitor deployments, and automate web hosting workflows directly from Autohive.

The integration uses Netlify API v1 with OAuth 2.0 authentication and implements 8 actions covering site management and deployments.

## Setup & Authentication

This integration uses **Platform OAuth 2.0** authentication, which provides a secure and seamless connection to your Netlify account.

### Connecting Your Netlify Account

1. Add the Netlify integration in Autohive
2. Click **Connect to Netlify**
3. You will be redirected to Netlify's authorization page
4. Sign in to your Netlify account (if not already signed in)
5. Review and authorize the requested permissions
6. You will be redirected back to Autohive with the connection complete

### Token Management

- **Automatic Token Refresh**: The platform automatically handles token refresh, so you don't need to worry about token expiration
- **Secure Storage**: Your OAuth tokens are securely stored and managed by the platform
- **Revocation**: To disconnect, you can revoke access from your Netlify account settings under **User Settings** > **Applications** > **Authorized applications**

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

Example successful response:
```json
{
  "result": true,
  "site": { "id": "abc123", "name": "my-site", "url": "https://my-site.netlify.app" }
}
```

Example error response:
```json
{
  "result": false,
  "error": "Site not found",
  "site": {}
}
```

## Actions

### Sites (5 actions)

#### `list_sites`
Lists all sites for the authenticated user.

**Inputs:** None

**Outputs:**
- `sites`: Array of site objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `create_site`
Creates a new site.

**Inputs:**
- `name` (required): Site name (will be used in the subdomain)
- `custom_domain` (optional): Custom domain for the site

**Outputs:**
- `site`: Created site object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_site`
Gets details of a specific site.

**Inputs:**
- `site_id` (required): The ID of the site

**Outputs:**
- `site`: Site object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `update_site`
Updates site settings.

**Inputs:**
- `site_id` (required): The ID of the site
- `name` (optional): New site name
- `custom_domain` (optional): New custom domain

**Outputs:**
- `site`: Updated site object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_site`
Deletes a site permanently.

**Inputs:**
- `site_id` (required): The ID of the site to delete

**Outputs:**
- `deleted`: Whether the site was deleted (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Deployments (3 actions)

#### `list_deploys`
Lists all deployments for a site.

**Inputs:**
- `site_id` (required): The ID of the site

**Outputs:**
- `deploys`: Array of deployment objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `create_deploy`
Creates a new deployment with files.

**Inputs:**
- `site_id` (required): The ID of the site
- `files` (required): Object mapping file paths to content
  - Example: `{"/index.html": "<html>...</html>", "/style.css": "body {...}"}`

**Outputs:**
- `deploy`: Deployment object with details
- `deploy_url`: URL of the deployed site
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Example:**
```json
{
  "site_id": "abc123",
  "files": {
    "/index.html": "<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>",
    "/styles/main.css": "body { font-family: sans-serif; }"
  }
}
```

---

#### `get_deploy`
Gets details of a specific deployment.

**Inputs:**
- `deploy_id` (required): The ID of the deployment

**Outputs:**
- `deploy`: Deployment object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v1
- **Base URL**: `https://api.netlify.com/api/v1`
- **Authentication**: OAuth 2.0 (Platform-managed)
- **Documentation**: https://docs.netlify.com/api/get-started/
- **Rate Limits**: 500 requests per minute

## Important Notes

- Site names must be unique across Netlify
- File paths in deployments should start with `/`
- Deployments use SHA1 hashing for file deduplication
- Large files may take longer to deploy
- Custom domains require DNS configuration

## Testing

To test the integration:

1. Navigate to the integration directory: `cd Netlify`
2. Install dependencies: `pip install -r requirements.txt`
3. Update test files with your access token and site IDs
4. Run tests: `python tests/test_netlify.py`

## Common Use Cases

**Static Site Hosting:**
1. Deploy static websites and landing pages
2. Host documentation sites
3. Deploy Single Page Applications (SPAs)
4. Host portfolio websites

**Continuous Deployment:**
1. Automate deployments from content changes
2. Deploy preview versions for review
3. Roll back to previous deployments
4. Monitor deployment status

**Site Management:**
1. Create sites programmatically
2. Update site configurations
3. Manage multiple sites
4. Clean up unused sites

## Version History

- **1.0.0** - Initial release with 8 actions
  - Sites: list, create, get, update, delete (5 actions)
  - Deploys: list, create, get (3 actions)

## Additional Resources

- [Netlify API Documentation](https://docs.netlify.com/api/get-started/)
- [Netlify CLI](https://docs.netlify.com/cli/get-started/)
- [Netlify Dev](https://www.netlify.com/products/dev/)

## Troubleshooting

### Common Issues

**401 Unauthorized:**
- Try reconnecting your Netlify account
- Ensure you have granted the required permissions
- Check if your Netlify account is still active

**404 Not Found:**
- Verify the site_id or deploy_id is correct
- Check that the resource exists

**Rate Limit Exceeded:**
- Wait before making more requests
- Implement request throttling in your workflows

**Deploy Failed:**
- Check file paths start with `/`
- Verify file content is valid
- Ensure files are not too large
