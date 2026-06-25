from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

google_search_console = Integration.load()


def build_credentials(context: ExecutionContext):
    access_token = context.auth.get("credentials", {}).get("access_token", "")
    creds = Credentials(token=access_token, token_uri="https://oauth2.googleapis.com/token")  # nosec B106
    return creds


def build_search_console_service(context: ExecutionContext):
    credentials = build_credentials(context)
    service = build("searchconsole", "v1", credentials=credentials)
    return service


@google_search_console.action("query_analytics")
class QueryAnalytics(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve search analytics data including queries, pages, countries, and devices."""
        try:
            service = build_search_console_service(context)
            site_url = inputs["site_url"]

            request_body = {
                "startDate": inputs["start_date"],
                "endDate": inputs["end_date"],
                "rowLimit": inputs.get("row_limit", 25000),
                "startRow": inputs.get("start_row", 0),
            }

            if inputs.get("dimensions"):
                request_body["dimensions"] = inputs["dimensions"]

            if inputs.get("dimension_filter_groups"):
                request_body["dimensionFilterGroups"] = inputs["dimension_filter_groups"]

            response = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()

            rows = []
            if "rows" in response:
                for row in response["rows"]:
                    row_dict = {}

                    if "keys" in row:
                        dimensions = inputs.get("dimensions", [])
                        for i, key in enumerate(row["keys"]):
                            if i < len(dimensions):
                                row_dict[dimensions[i]] = key

                    row_dict["clicks"] = row.get("clicks", 0)
                    row_dict["impressions"] = row.get("impressions", 0)
                    row_dict["ctr"] = row.get("ctr", 0)
                    row_dict["position"] = row.get("position", 0)

                    rows.append(row_dict)

            return ActionResult(data={"rows": rows, "row_count": len(rows)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@google_search_console.action("list_sites")
class ListSites(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """List all sites in the user's Search Console account."""
        try:
            service = build_search_console_service(context)

            response = service.sites().list().execute()

            sites = []
            if "siteEntry" in response:
                for site in response["siteEntry"]:
                    sites.append(
                        {"site_url": site.get("siteUrl", ""), "permission_level": site.get("permissionLevel", "")}
                    )

            return ActionResult(data={"sites": sites, "site_count": len(sites)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@google_search_console.action("inspect_url")
class InspectURL(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get URL inspection data including index status, mobile usability, and more."""
        try:
            credentials = build_credentials(context)
            service = build("searchconsole", "v1", credentials=credentials)

            site_url = inputs["site_url"]
            inspection_url = inputs["inspection_url"]

            request_body = {"inspectionUrl": inspection_url, "siteUrl": site_url}

            response = service.urlInspection().index().inspect(body=request_body).execute()

            return ActionResult(data={"inspection_result": response.get("inspectionResult", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@google_search_console.action("list_sitemaps")
class ListSitemaps(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """List all sitemaps for a site."""
        try:
            service = build_search_console_service(context)
            site_url = inputs["site_url"]

            response = service.sitemaps().list(siteUrl=site_url).execute()

            sitemaps = []
            if "sitemap" in response:
                for sitemap in response["sitemap"]:
                    sitemaps.append(
                        {
                            "path": sitemap.get("path", ""),
                            "last_submitted": sitemap.get("lastSubmitted", ""),
                            "is_pending": sitemap.get("isPending", False),
                            "is_sitemap_index": sitemap.get("isSitemapsIndex", False),
                        }
                    )

            return ActionResult(data={"sitemaps": sitemaps, "sitemap_count": len(sitemaps)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@google_search_console.action("get_sitemap")
class GetSitemap(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get detailed information about a specific sitemap."""
        try:
            service = build_search_console_service(context)
            site_url = inputs["site_url"]
            sitemap_url = inputs["sitemap_url"]

            response = service.sitemaps().get(siteUrl=site_url, feedpath=sitemap_url).execute()

            return ActionResult(data={"sitemap": response}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
