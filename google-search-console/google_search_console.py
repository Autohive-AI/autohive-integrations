from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any, List
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

google_search_console = Integration.load()

def build_credentials(context: ExecutionContext):
    """Build Google credentials from ExecutionContext.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        Google credentials object
    """
    access_token = context.auth['credentials']['access_token']

    creds = Credentials(
        token=access_token,
        token_uri='https://oauth2.googleapis.com/token'
    )

    return creds

def build_search_console_service(context: ExecutionContext):
    """Build Google Search Console API service.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        Search Console service instance
    """
    credentials = build_credentials(context)
    service = build('searchconsole', 'v1', credentials=credentials)
    return service

@google_search_console.action("query_analytics")
class QueryAnalytics(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve search analytics data including queries, pages, countries, and devices."""
        try:
            service = build_search_console_service(context)
            site_url = inputs['site_url']

            # Build the request body
            request_body = {
                'startDate': inputs['start_date'],
                'endDate': inputs['end_date'],
                'rowLimit': inputs.get('row_limit', 25000),
                'startRow': inputs.get('start_row', 0)
            }

            # Add dimensions if provided
            if 'dimensions' in inputs and inputs['dimensions']:
                request_body['dimensions'] = inputs['dimensions']

            # Add dimension filters if provided
            if 'dimension_filter_groups' in inputs and inputs['dimension_filter_groups']:
                request_body['dimensionFilterGroups'] = inputs['dimension_filter_groups']

            # Execute request
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()

            # Format response
            rows = []
            if 'rows' in response:
                for row in response['rows']:
                    row_dict = {}

                    # Add dimension values
                    if 'keys' in row:
                        dimensions = inputs.get('dimensions', [])
                        for i, key in enumerate(row['keys']):
                            if i < len(dimensions):
                                row_dict[dimensions[i]] = key

                    # Add metric values
                    row_dict['clicks'] = row.get('clicks', 0)
                    row_dict['impressions'] = row.get('impressions', 0)
                    row_dict['ctr'] = row.get('ctr', 0)
                    row_dict['position'] = row.get('position', 0)

                    rows.append(row_dict)

            return ActionResult(
                data={
                    "rows": rows,
                    "row_count": len(rows),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "rows": [],
                    "row_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_search_console.action("list_sites")
class ListSites(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """List all sites in the user's Search Console account."""
        try:
            service = build_search_console_service(context)

            # Execute request
            response = service.sites().list().execute()

            # Format response
            sites = []
            if 'siteEntry' in response:
                for site in response['siteEntry']:
                    sites.append({
                        'site_url': site.get('siteUrl', ''),
                        'permission_level': site.get('permissionLevel', '')
                    })

            return ActionResult(
                data={
                    "sites": sites,
                    "site_count": len(sites),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "sites": [],
                    "site_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_search_console.action("inspect_url")
class InspectURL(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get URL inspection data including index status, mobile usability, and more."""
        try:
            credentials = build_credentials(context)

            # URL Inspection API requires a different service
            service = build('searchconsole', 'v1', credentials=credentials)

            site_url = inputs['site_url']
            inspection_url = inputs['inspection_url']

            # Build request body
            request_body = {
                'inspectionUrl': inspection_url,
                'siteUrl': site_url
            }

            # Execute request
            response = service.urlInspection().index().inspect(
                body=request_body
            ).execute()

            return ActionResult(
                data={
                    "inspection_result": response.get('inspectionResult', {}),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "inspection_result": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_search_console.action("list_sitemaps")
class ListSitemaps(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """List all sitemaps for a site."""
        try:
            service = build_search_console_service(context)
            site_url = inputs['site_url']

            # Execute request
            response = service.sitemaps().list(siteUrl=site_url).execute()

            # Format response
            sitemaps = []
            if 'sitemap' in response:
                for sitemap in response['sitemap']:
                    sitemaps.append({
                        'path': sitemap.get('path', ''),
                        'last_submitted': sitemap.get('lastSubmitted', ''),
                        'is_pending': sitemap.get('isPending', False),
                        'is_sitemap_index': sitemap.get('isSitemapsIndex', False)
                    })

            return ActionResult(
                data={
                    "sitemaps": sitemaps,
                    "sitemap_count": len(sitemaps),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "sitemaps": [],
                    "sitemap_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_search_console.action("get_sitemap")
class GetSitemap(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get detailed information about a specific sitemap."""
        try:
            service = build_search_console_service(context)
            site_url = inputs['site_url']
            sitemap_url = inputs['sitemap_url']

            # Execute request
            response = service.sitemaps().get(
                siteUrl=site_url,
                feedpath=sitemap_url
            ).execute()

            return ActionResult(
                data={
                    "sitemap": response,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "sitemap": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )
