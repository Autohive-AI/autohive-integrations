import asyncio
from typing import Any, Dict, Optional
import json

from context import google_looker  # integration instance


class MockResponse:
    """Mimics the production Lambda wrapper's fetch response shape."""

    def __init__(self, data, status=200):
        self.data = data
        self.status = status


class MockExecutionContext:
    def __init__(self, responses: Dict[str, Any]):
        self.auth = {
            "credentials": {
                "base_url": "https://test-looker.looker.com",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",  # nosec B105
            }
        }
        self._responses = responses
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json: Any = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        self._requests.append(
            {
                "url": url,
                "method": method,
                "params": params,
                "json": json,
                "data": data,
                "headers": headers,
            }
        )
        # Route by endpoint suffix for simplicity
        if "/api/4.0/login" in url and method == "POST":
            return MockResponse(
                self._responses.get(
                    "POST /login",
                    {"access_token": "mock_token_123", "expires_in": 3600},  # nosec B105
                )
            )
        if "/api/4.0/dashboards/" in url and method == "GET":
            return MockResponse(self._responses.get("GET /dashboard", {"dashboard": {}}))
        if "/api/4.0/dashboards" in url and method == "GET":
            return MockResponse(self._responses.get("GET /dashboards", []))
        if "/api/4.0/lookml_models/" in url and method == "GET":
            return MockResponse(self._responses.get("GET /model", {"model": {}}))
        if "/api/4.0/lookml_models" in url and method == "GET":
            return MockResponse(self._responses.get("GET /models", []))
        if "/api/4.0/queries" in url and method == "POST":
            return MockResponse(self._responses.get("POST /queries", {"id": "mock_query_123"}))
        if "/api/4.0/queries/" in url and "/run/" in url and method == "GET":
            return MockResponse(self._responses.get("GET /query_results", [{"result": "data"}]))
        if "/api/4.0/sql_queries/" in url and "/run/" in url and method == "POST":
            return MockResponse(self._responses.get("POST /sql_results", [{"sql_result": "data"}]))
        if "/api/4.0/sql_queries" in url and method == "POST":
            return MockResponse(self._responses.get("POST /sql_queries", {"slug": "mock_sql_123"}))
        if "/api/4.0/connections" in url and method == "GET":
            return MockResponse(self._responses.get("GET /connections", []))
        return MockResponse({})


async def test_list_dashboards_basic():
    responses = {
        "GET /dashboards": [
            {
                "id": "1",
                "title": "Sales Dashboard",
                "description": "Track sales metrics",
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": "2",
                "title": "Marketing Dashboard",
                "description": "Marketing performance",
                "created_at": "2025-01-02T00:00:00Z",
            },
        ]
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action("list_dashboards", {}, context)
    data = integration_result.result.data
    assert data["result"] is True
    assert "dashboards" in data
    assert len(data["dashboards"]) == 2
    assert data["dashboards"][0]["title"] == "Sales Dashboard"


async def test_get_dashboard():
    responses = {
        "GET /dashboard": {
            "id": "123",
            "title": "Test Dashboard",
            "description": "A test dashboard",
            "dashboard_elements": [{"id": "elem1", "type": "looker_line", "query": {"id": "query1"}}],
        }
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action("get_dashboard", {"dashboard_id": "123"}, context)
    data = integration_result.result.data
    assert data["result"] is True
    assert data["dashboard"]["id"] == "123"
    assert data["dashboard"]["title"] == "Test Dashboard"


async def test_execute_lookml_query():
    responses = {
        "POST /queries": {"id": "query_456"},
        "GET /query_results": [
            {"dimension1": "value1", "measure1": 100},
            {"dimension1": "value2", "measure1": 200},
        ],
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action(
        "execute_lookml_query",
        {
            "model": "sales_model",
            "explore": "orders",
            "dimensions": ["orders.status"],
            "measures": ["orders.count"],
            "limit": 100,
        },
        context,
    )
    data = integration_result.result.data
    assert data["result"] is True
    assert "query_results" in data
    query_data = json.loads(data["query_results"])
    assert len(query_data) == 2
    assert query_data[0]["measure1"] == 100

    # Verify payload sent to POST /queries
    query_calls = [r for r in context._requests if "/api/4.0/queries" in r["url"] and r["method"] == "POST"]
    assert len(query_calls) == 1
    payload = query_calls[0]["json"]
    assert payload["model"] == "sales_model"
    assert payload["view"] == "orders"
    assert "explore" not in payload
    assert payload["fields"] == ["orders.status", "orders.count"]
    assert "dimensions" not in payload
    assert "measures" not in payload
    assert payload["limit"] == "100"
    assert isinstance(payload["limit"], str)


async def test_execute_lookml_query_dimensions_only():
    responses = {
        "POST /queries": {"id": "query_789"},
        "GET /query_results": [{"dim1": "val1"}],
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action(
        "execute_lookml_query",
        {
            "model": "my_model",
            "explore": "my_explore",
            "dimensions": ["view.dim1", "view.dim2"],
        },
        context,
    )
    data = integration_result.result.data
    assert data["result"] is True

    query_calls = [r for r in context._requests if "/api/4.0/queries" in r["url"] and r["method"] == "POST"]
    payload = query_calls[0]["json"]
    assert payload["fields"] == ["view.dim1", "view.dim2"]
    assert "dimensions" not in payload
    assert "measures" not in payload


async def test_execute_lookml_query_measures_only():
    responses = {
        "POST /queries": {"id": "query_790"},
        "GET /query_results": [{"count": 42}],
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action(
        "execute_lookml_query",
        {
            "model": "my_model",
            "explore": "my_explore",
            "measures": ["view.count"],
        },
        context,
    )
    data = integration_result.result.data
    assert data["result"] is True

    query_calls = [r for r in context._requests if "/api/4.0/queries" in r["url"] and r["method"] == "POST"]
    payload = query_calls[0]["json"]
    assert payload["fields"] == ["view.count"]
    assert "dimensions" not in payload
    assert "measures" not in payload


async def test_execute_lookml_query_no_fields():
    responses = {
        "POST /queries": {"id": "query_791"},
        "GET /query_results": [],
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action(
        "execute_lookml_query",
        {
            "model": "my_model",
            "explore": "my_explore",
        },
        context,
    )
    data = integration_result.result.data
    assert data["result"] is True

    query_calls = [r for r in context._requests if "/api/4.0/queries" in r["url"] and r["method"] == "POST"]
    payload = query_calls[0]["json"]
    assert "fields" not in payload
    assert "dimensions" not in payload
    assert "measures" not in payload


async def test_list_models():
    responses = {
        "GET /models": [
            {
                "name": "sales",
                "label": "Sales Model",
                "explores": ["orders", "customers"],
            },
            {
                "name": "marketing",
                "label": "Marketing Model",
                "explores": ["campaigns"],
            },
        ]
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action("list_models", {}, context)
    data = integration_result.result.data
    assert data["result"] is True
    assert len(data["models"]) == 2
    assert data["models"][0]["name"] == "sales"


async def test_get_model():
    responses = {
        "GET /model": {
            "name": "sales",
            "label": "Sales Model",
            "explores": [
                {"name": "orders", "label": "Orders"},
                {"name": "customers", "label": "Customers"},
            ],
        }
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action("get_model", {"model_name": "sales"}, context)
    data = integration_result.result.data
    assert data["result"] is True
    assert data["model"]["name"] == "sales"
    assert len(data["model"]["explores"]) == 2


async def test_execute_sql_query():
    responses = {
        "POST /sql_queries": {"slug": "sql_789"},
        "POST /sql_results": [
            {"column1": "row1_val1", "column2": "row1_val2"},
            {"column1": "row2_val1", "column2": "row2_val2"},
        ],
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action(
        "execute_sql_query",
        {"sql": "SELECT * FROM orders LIMIT 10", "connection_name": "warehouse"},
        context,
    )
    data = integration_result.result.data
    assert data["result"] is True
    assert data["slug"] == "sql_789"
    query_data = json.loads(data["query_results"]) if data["query_results"] else []
    assert len(query_data) == 2


async def test_list_connections():
    responses = {
        "GET /connections": [
            {"name": "warehouse", "database": "bigquery", "dialect_name": "bigquery"},
            {"name": "analytics", "database": "postgres", "dialect_name": "postgres"},
        ]
    }
    context = MockExecutionContext(responses)
    integration_result = await google_looker.execute_action("list_connections", {}, context)
    data = integration_result.result.data
    assert data["result"] is True
    assert len(data["connections"]) == 2
    assert data["connections"][0]["name"] == "warehouse"


async def test_authentication_error():
    class FailAuthContext(MockExecutionContext):
        async def fetch(self, url: str, method: str = "GET", **kwargs):
            if "/api/4.0/login" in url:
                raise Exception("Invalid credentials")
            return await super().fetch(url, method, **kwargs)

    context = FailAuthContext({})
    integration_result = await google_looker.execute_action("list_dashboards", {}, context)
    data = integration_result.result.data
    assert data["result"] is False
    assert "error" in data
    assert "Invalid credentials" in data["error"]


async def test_missing_credentials():
    class NoAuthContext:
        def __init__(self):
            self.auth = {}

    context = NoAuthContext()
    integration_result = await google_looker.execute_action("list_dashboards", {}, context)
    data = integration_result.result.data
    assert data["result"] is False
    assert "error" in data
    assert "authentication credentials" in data["error"].lower()


async def test_execute_lookml_query_missing_required_fields():
    context = MockExecutionContext({})
    integration_result = await google_looker.execute_action(
        "execute_lookml_query", {"dimensions": ["orders.status"]}, context
    )
    # SDK returns a validation error dict (not ActionResult) for schema violations
    error_data = integration_result.result
    assert isinstance(error_data, dict)
    assert "model" in error_data["message"] or "explore" in error_data["message"]
    assert error_data["source"] == "input"


async def test_execute_sql_query_missing_connection():
    context = MockExecutionContext({})
    integration_result = await google_looker.execute_action(
        "execute_sql_query", {"sql": "SELECT * FROM orders"}, context
    )
    data = integration_result.result.data
    assert data["result"] is False
    assert "error" in data
    assert "connection_name" in data["error"] or "model_name" in data["error"]


def _run(coro):
    return asyncio.run(coro)


if __name__ == "__main__":
    _run(test_list_dashboards_basic())
    _run(test_get_dashboard())
    _run(test_execute_lookml_query())
    _run(test_execute_lookml_query_dimensions_only())
    _run(test_execute_lookml_query_measures_only())
    _run(test_execute_lookml_query_no_fields())
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
