from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

config_path = os.path.join(os.path.dirname(__file__), "config.json")
google_looker = Integration.load(config_path)

class LookerAPIHelper:
    
    def __init__(self, context: ExecutionContext, base_url: str, client_id: str, client_secret: str):
        self.context = context
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
    
    async def _get_access_token(self) -> str:
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
            
        auth_url = f"{self.base_url}/api/4.0/login"
        auth_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        try:
            response = await self.context.fetch(
                url=auth_url,
                method="POST",
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if isinstance(response, dict):
                token_data = response
            else:
                if response.status_code != 200:
                    raise Exception(f"Authentication failed with status {response.status_code}: {response.text}")
                token_data = response.json()
            
            self.access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            if not self.access_token:
                raise Exception("No access_token received in authentication response")
            
            return self.access_token
            
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")
    
    async def _get_headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/api/4.0{endpoint}"
        headers = await self._get_headers()
        
        try:
            response = await self.context.fetch(
                url=url,
                method=method.upper(),
                json=data if method.upper() in ["POST", "PUT"] else None,
                params=params,
                headers=headers
            )
            
            if isinstance(response, (dict, list)):
                return response
            else:
                if response.status_code not in [200, 201, 202, 204]:
                    raise Exception(f"API request failed: {response.status_code} - {response.text}")
                
                return response.json() if response.text else {}
            
        except Exception as e:
            raise

def build_looker_helper(context: ExecutionContext) -> LookerAPIHelper:
    try:
        if hasattr(context, 'auth') and context.auth:
            credentials = context.auth.get("credentials", {})
            base_url = credentials.get('base_url')
            client_id = credentials.get('client_id')
            client_secret = credentials.get('client_secret')
        else:
            raise ValueError("No authentication credentials provided in context")
        
        if not all([base_url, client_id, client_secret]):
            missing = []
            if not base_url: missing.append("base_url")
            if not client_id: missing.append("client_id")
            if not client_secret: missing.append("client_secret")
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return LookerAPIHelper(context, base_url, client_id, client_secret)
    
    except Exception as e:
        raise Exception(f"Failed to build Looker helper: {str(e)}")

@google_looker.action("list_dashboards")
class ListDashboards(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            
            params = {}
            if 'fields' in inputs:
                params['fields'] = inputs['fields']
            if 'page' in inputs:
                params['page'] = inputs['page']
            if 'per_page' in inputs:
                params['per_page'] = inputs['per_page']
            
            dashboards = await helper.make_request("GET", "/dashboards", params=params)
            
            return {
                "dashboards": dashboards,
                "result": True
            }
            
        except Exception as e:
            return {
                "dashboards": [],
                "result": False,
                "error": str(e)
            }

@google_looker.action("get_dashboard")
class GetDashboard(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            dashboard_id = inputs['dashboard_id']
            
            params = {}
            if 'fields' in inputs:
                params['fields'] = inputs['fields']
            
            dashboard = await helper.make_request("GET", f"/dashboards/{dashboard_id}", params=params)
            
            return {
                "dashboard": dashboard,
                "result": True
            }
            
        except Exception as e:
            return {
                "dashboard": {},
                "result": False,
                "error": str(e)
            }

@google_looker.action("execute_lookml_query")
class ExecuteLookMLQuery(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            
            query_data = {
                "model": inputs['model'],
                "explore": inputs['explore']
            }
            
            if 'dimensions' in inputs:
                query_data['dimensions'] = inputs['dimensions']
            if 'measures' in inputs:
                query_data['measures'] = inputs['measures']
            if 'filters' in inputs:
                query_data['filters'] = inputs['filters']
            if 'sorts' in inputs:
                query_data['sorts'] = inputs['sorts']
            if 'limit' in inputs:
                query_data['limit'] = inputs['limit']
            
            query = await helper.make_request("POST", "/queries", data=query_data)
            query_id = query.get('id')
            
            if not query_id:
                raise Exception("No query ID returned from query creation")
            
            result_format = inputs.get('result_format', 'json')
            params = {
                'result_format': result_format
            }
            if 'apply_formatting' in inputs:
                params['apply_formatting'] = inputs['apply_formatting']
            if 'apply_vis' in inputs:
                params['apply_vis'] = inputs['apply_vis']
            
            results = await helper.make_request("GET", f"/queries/{query_id}/run/{result_format}", params=params)
            
            return {
                "query_results": json.dumps(results) if isinstance(results, (dict, list)) else str(results),
                "result": True
            }
            
        except Exception as e:
            return {
                "query_results": "[]",
                "result": False,
                "error": str(e)
            }

@google_looker.action("list_models")
class ListModels(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            
            params = {}
            if 'fields' in inputs:
                params['fields'] = inputs['fields']
            
            models = await helper.make_request("GET", "/lookml_models", params=params)
            
            return {
                "models": models,
                "result": True
            }
            
        except Exception as e:
            return {
                "models": [],
                "result": False,
                "error": str(e)
            }

@google_looker.action("get_model")
class GetModel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            model_name = inputs['model_name']
            
            params = {}
            if 'fields' in inputs:
                params['fields'] = inputs['fields']
            
            model = await helper.make_request("GET", f"/lookml_models/{model_name}", params=params)
            
            return {
                "model": model,
                "result": True
            }
            
        except Exception as e:
            return {
                "model": {},
                "result": False,
                "error": str(e)
            }

@google_looker.action("execute_sql_query")
class ExecuteSQLQuery(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            
            sql_query_data = {
                "sql": inputs['sql']
            }
            
            if 'connection_name' in inputs:
                sql_query_data['connection_name'] = inputs['connection_name']
            elif 'model_name' in inputs:
                sql_query_data['model_name'] = inputs['model_name']
            else:
                raise ValueError("Either 'connection_name' or 'model_name' must be provided")
            
            if 'vis_config' in inputs:
                sql_query_data['vis_config'] = inputs['vis_config']
            if 'slug' in inputs:
                sql_query_data['slug'] = inputs['slug']
            
            sql_query = await helper.make_request("POST", "/sql_queries", data=sql_query_data)
            
            slug = sql_query.get('slug')
            if not slug:
                raise Exception("No slug returned from SQL query creation")
            
            result_format = inputs.get('result_format', 'json')
            params = {}
            if 'download' in inputs:
                params['download'] = inputs['download']
            
            results = await helper.make_request("POST", f"/sql_queries/{slug}/run/{result_format}", params=params)
            
            return {
                "slug": slug,
                "query_results": json.dumps(results) if isinstance(results, (dict, list)) else str(results),
                "result": True
            }
            
        except Exception as e:
            return {
                "slug": "",
                "query_results": "",
                "result": False,
                "error": str(e)
            }

@google_looker.action("list_connections")
class ListConnections(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            helper = build_looker_helper(context)
            
            params = {}
            if 'fields' in inputs:
                params['fields'] = inputs['fields']
            
            connections = await helper.make_request("GET", "/connections", params=params)
            
            return {
                "connections": connections,
                "result": True
            }
            
        except Exception as e:
            return {
                "connections": [],
                "result": False,
                "error": str(e)
            }