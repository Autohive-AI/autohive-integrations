import asyncio
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import json

from context import google_looker  # integration instance


class MockExecutionContext:
    def __init__(self, responses: Dict[str, Any]):
        # mimic SDK context shape expected by google_looker.py
        self.auth = {
            "credentials": {
                "base_url": "https://test-looker.looker.com",
                "client_id": "test_client_id", 
                "client_secret": "test_client_secret"
            }
        }
        self._responses = responses

    async def fetch(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, json: Any = None, data: Any = None, headers: Optional[Dict[str, str]] = None, **kwargs):
        # Route by endpoint suffix for simplicity
        if "/api/4.0/login" in url and method == "POST":
            return self._responses.get("POST /login", {
                "access_token": "mock_token_123",
                "expires_in": 3600
            })
        if "/api/4.0/dashboards/" in url and method == "GET":
            return self._responses.get("GET /dashboard", {"dashboard": {}})
        if "/api/4.0/dashboards" in url and method == "GET":
            return self._responses.get("GET /dashboards", [])
        if "/api/4.0/lookml_models/" in url and method == "GET":
            return self._responses.get("GET /model", {"model": {}})
        if "/api/4.0/lookml_models" in url and method == "GET":
            return self._responses.get("GET /models", [])
        if "/api/4.0/queries" in url and method == "POST":
            return self._responses.get("POST /queries", {"id": "mock_query_123"})
        if "/api/4.0/queries/" in url and "/run/" in url and method == "GET":
            return self._responses.get("GET /query_results", [{"result": "data"}])
        if "/api/4.0/sql_queries/" in url and "/run/" in url and method == "POST":
            return self._responses.get("POST /sql_results", [{"sql_result": "data"}])
        if "/api/4.0/sql_queries" in url and method == "POST":
            return self._responses.get("POST /sql_queries", {"slug": "mock_sql_123"})
        if "/api/4.0/connections" in url and method == "GET":
            return self._responses.get("GET /connections", [])
        return {}


async def test_list_dashboards_basic():
    responses = {
        "GET /dashboards": [
            {
                "id": "1",
                "title": "Sales Dashboard",
                "description": "Track sales metrics",
                "created_at": "2025-01-01T00:00:00Z"
            },
            {
                "id": "2", 
                "title": "Marketing Dashboard",
                "description": "Marketing performance",
                "created_at": "2025-01-02T00:00:00Z"
            }
        ]
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("list_dashboards", {}, context)
    assert result["result"] is True
    assert "dashboards" in result
    assert len(result["dashboards"]) == 2
    assert result["dashboards"][0]["title"] == "Sales Dashboard"


async def test_get_dashboard():
    responses = {
        "GET /dashboard": {
            "id": "123",
            "title": "Test Dashboard", 
            "description": "A test dashboard",
            "dashboard_elements": [
                {"id": "elem1", "type": "looker_line", "query": {"id": "query1"}}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("get_dashboard", {"dashboard_id": "123"}, context)
    assert result["result"] is True
    assert result["dashboard"]["id"] == "123"
    assert result["dashboard"]["title"] == "Test Dashboard"


async def test_execute_lookml_query():
    responses = {
        "POST /queries": {"id": "query_456"},
        "GET /query_results": [
            {"dimension1": "value1", "measure1": 100},
            {"dimension1": "value2", "measure1": 200}
        ]
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("execute_lookml_query", {
        "model": "sales_model",
        "explore": "orders", 
        "dimensions": ["orders.status"],
        "measures": ["orders.count"],
        "limit": 100
    }, context)
    assert result["result"] is True
    assert "query_results" in result
    query_data = json.loads(result["query_results"])
    assert len(query_data) == 2
    assert query_data[0]["measure1"] == 100


async def test_list_models():
    responses = {
        "GET /models": [
            {"name": "sales", "label": "Sales Model", "explores": ["orders", "customers"]},
            {"name": "marketing", "label": "Marketing Model", "explores": ["campaigns"]}
        ]
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("list_models", {}, context)
    assert result["result"] is True
    assert len(result["models"]) == 2
    assert result["models"][0]["name"] == "sales"


async def test_get_model():
    responses = {
        "GET /model": {
            "name": "sales",
            "label": "Sales Model", 
            "explores": [
                {"name": "orders", "label": "Orders"},
                {"name": "customers", "label": "Customers"}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("get_model", {"model_name": "sales"}, context)
    assert result["result"] is True
    assert result["model"]["name"] == "sales"
    assert len(result["model"]["explores"]) == 2


async def test_execute_sql_query():
    responses = {
        "POST /sql_queries": {"slug": "sql_789"},
        "POST /sql_results": [
            {"column1": "row1_val1", "column2": "row1_val2"},
            {"column1": "row2_val1", "column2": "row2_val2"}
        ]
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("execute_sql_query", {
        "sql": "SELECT * FROM orders LIMIT 10",
        "connection_name": "warehouse"
    }, context)
    assert result["result"] is True
    assert result["slug"] == "sql_789"
    query_data = json.loads(result["query_results"]) if result["query_results"] else []
    assert len(query_data) == 2


async def test_list_connections():
    responses = {
        "GET /connections": [
            {"name": "warehouse", "database": "bigquery", "dialect_name": "bigquery"},
            {"name": "analytics", "database": "postgres", "dialect_name": "postgres"}
        ]
    }
    context = MockExecutionContext(responses)
    result = await google_looker.execute_action("list_connections", {}, context)
    assert result["result"] is True
    assert len(result["connections"]) == 2
    assert result["connections"][0]["name"] == "warehouse"


async def test_authentication_error():
    # Test when authentication fails
    class FailAuthContext(MockExecutionContext):
        async def fetch(self, url: str, method: str = "GET", **kwargs):
            if "/api/4.0/login" in url:
                raise Exception("Invalid credentials")
            return super().fetch(url, method, **kwargs)
    
    context = FailAuthContext({})
    result = await google_looker.execute_action("list_dashboards", {}, context)
    assert result["result"] is False
    assert "error" in result
    assert "Invalid credentials" in result["error"]


async def test_missing_credentials():
    # Test when no auth credentials provided
    class NoAuthContext:
        def __init__(self):
            self.auth = {}
    
    context = NoAuthContext()
    result = await google_looker.execute_action("list_dashboards", {}, context)
    assert result["result"] is False
    assert "error" in result
    assert "authentication credentials" in result["error"].lower()


async def test_execute_lookml_query_missing_required_fields():
    context = MockExecutionContext({})
    # Missing required model and explore fields - should raise ValidationError
    try:
        result = await google_looker.execute_action("execute_lookml_query", {
            "dimensions": ["orders.status"]
        }, context)
        assert False, "Should have raised ValidationError"
    except Exception as e:
        assert "required" in str(e).lower()
        assert "model" in str(e) or "explore" in str(e)


async def test_execute_sql_query_missing_connection():
    context = MockExecutionContext({})
    # Missing both connection_name and model_name
    result = await google_looker.execute_action("execute_sql_query", {
        "sql": "SELECT * FROM orders"
    }, context)
    assert result["result"] is False
    assert "error" in result
    assert "connection_name" in result["error"] or "model_name" in result["error"]


def _run(coro):
    return asyncio.run(coro)


if __name__ == "__main__":
    _run(test_list_dashboards_basic())
    _run(test_get_dashboard())
    _run(test_execute_lookml_query())
    _run(test_list_models())
    _run(test_get_model())
    _run(test_execute_sql_query())
    _run(test_list_connections())
    # Error handling tests
    _run(test_authentication_error())
    _run(test_missing_credentials())
    _run(test_execute_lookml_query_missing_required_fields())
    _run(test_execute_sql_query_missing_connection())
    print("All Google Looker integration tests passed")