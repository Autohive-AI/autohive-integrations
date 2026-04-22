# Test Stocktake Report

**Date:** 2026-04-14  
**Scope:** All 86 integrations in `autohive-integrations`

---

## Executive Summary

Every integration has a `tests/` directory with the required scaffolding (`__init__.py`, `context.py`, `test_*.py`). However, **the vast majority of tests are manual integration-test scripts** that require real API credentials to run. Only a small minority use mocks, and almost none can run in CI. There is **no automated test execution in CI** — the existing CI only validates structure, linting, and config correctness.

---

## Numbers at a Glance

| Metric | Count |
|---|---|
| Total integrations | 86 |
| Integrations with `tests/` directory | 86 (100%) |
| Integrations with `context.py` | 86 (100%) |
| Integrations with `__init__.py` | 89* |
| Total `test_*.py` files | 115 |
| Total lines of test code | ~54,400 |
| Tests using **mocks** (runnable without credentials) | 14 (16%) |
| Tests using **pytest** (`@pytest.mark`, fixtures) | 9 (10%) |
| Tests that are **manual runners** (`asyncio.run(main())`) | ~72 (84%) |
| Tests with a **custom test runner** (no framework) | 2 |
| Tests requiring **real API keys/tokens** | ~72 (84%) |
| CI workflows that **execute tests** | **0** |

\* Some integrations have extra `__init__.py` files from nested test directories.

---

## Test Style Breakdown

### 1. Manual Integration Test Runners (~84% of tests)

The dominant pattern. These are `async def main()` scripts run via `python test_*.py` with real credentials passed as args or env vars.

**Example:** `stripe/tests/test_stripe.py` (727 lines)
```
python test_stripe.py sk_test_xxx          # Full CRUD suite
python test_stripe.py sk_test_xxx --quick  # Read-only tests
```

**Characteristics:**
- Require real API credentials (env vars or CLI args)
- Use `ExecutionContext(auth=...)` directly
- Print results to stdout; no structured pass/fail
- Cannot run in CI without secrets
- No assertions in many cases — just print output and catch exceptions
- Follow the SDK template pattern exactly

**Integrations using this pattern:** hackernews, stripe, box, google-analytics, google-calendar, asana, clickup, notion (partially), zoom, xero (partially), and ~60 more.

### 2. Pytest-Based Mocked Unit Tests (~10% of tests)

Proper unit tests using `pytest`, `@pytest.mark.asyncio`, `unittest.mock.AsyncMock`, and `MagicMock`. These can run without credentials.

**Example:** `shopify-customer/tests/test_unit.py` (305 lines)
```python
@pytest.fixture
def mock_context():
    context = MagicMock()
    context.auth = {"credentials": {"access_token": "test_token_123"}}
    context.fetch = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_get_profile_success(self, mock_context):
    mock_context.fetch.return_value = {"data": {"customer": {...}}}
    result = await shopify_customer.execute_action("customer_get_profile", {}, mock_context)
    assert result.result.data["success"] is True
```

**Integrations with pytest mocked tests:**
- `shopify-customer` (test_unit.py)
- `xero` (rate limiter + purchase order tests)
- `uber`
- `linkedin`, `linkedin-ads`
- `microsoft-word`, `microsoft-powerpoint`
- `productboard`
- `instagram`, `tiktok`
- `facebook`, `humanitix`
- `spreadsheet-tools`

### 3. Hybrid Tests (pytest + manual runner) — 2 integrations

Files that contain both `@pytest.mark.asyncio` test functions and a `main()` with `asyncio.run()`. The pytest tests use mocks; the `main()` uses real credentials.

**Examples:** `xero/tests/test_xero.py`, `spreadsheet-tools/tests/test_spreadsheet_tools.py`

### 4. Custom Test Runner — 2 integrations

Home-grown test harnesses without pytest or unittest.

**Examples:**
- `slider/tests/test_unit_all.py` — custom `TestRunner` class with `[PASS]/[FAIL]` output
- `doc-maker/tests/test_unit.py` — custom `TestResult` class with `assert_equal`/`assert_true`

### 5. Mocked Tests Without pytest Framework — 3 integrations

Use `unittest.mock` but run via `asyncio.run(main())` instead of pytest.

**Examples:** `notion/tests/test_notion_integration.py`, `powerbi/tests/test_powerbi_integration.py`, `monday-com/tests/test_monday_com.py`

---

## What Tests Actually Validate

| What's tested | How many integrations | Notes |
|---|---|---|
| Action execution against **live API** | ~72 | Requires real credentials |
| Action execution against **mocked API** | ~14 | Can run offline |
| Handler logic / helper functions | ~5 | slider, doc-maker, shopify-customer |
| Config schema correctness | ~3 | notion, gong — verify config.json matches handlers |
| Error handling / edge cases | ~8 | xero rate limiting, notion errors, shopify validation |
| Connected account handler | ~5 | zoom, uber — test `get_connected_account` |
| **No meaningful test logic** | 0 | All 86 have at least basic smoke tests |

---

## CI/CD Situation

### What CI does today (`validate-integration.yml`)
- ✅ Folder structure validation (required files present)
- ✅ `config.json` schema validation
- ✅ Python syntax + import resolution
- ✅ ruff lint + format
- ✅ bandit security scan
- ✅ pip-audit dependency check
- ✅ Config-code sync check

### What CI does NOT do
- ❌ **No test execution** — `pytest` is never run
- ❌ No coverage reporting
- ❌ No mock test discovery/execution
- ❌ No validation that tests actually pass

---

## Credential Exposure Concerns

14 test files reference API keys/tokens via environment variables or placeholder strings. These use patterns like:
```python
API_KEY = os.environ.get("STRIPE_TEST_API_KEY", "sk_test_your_key_here")
ACCESS_TOKEN = os.environ.get("ZOOM_ACCESS_TOKEN", "")
```

No hardcoded real secrets were found — all use env var lookups with placeholder defaults. This is the correct pattern but means none of these tests are runnable without manual setup.

---

## SDK Template Compliance

The SDK template (`samples/template/`) prescribes:
- `tests/__init__.py` — ✅ present in all 86
- `tests/context.py` — ✅ present in all 86
- `tests/test_*.py` — ✅ present in all 86
- Manual `asyncio.run()` runner style — ✅ used by ~84%

The SDK does **not** mandate pytest or any test framework. The template uses plain async functions with `asyncio.run()`. Most integrations follow this exactly.

---

## Key Observations

1. **No tests run in CI.** The biggest gap. 86 integrations, 115 test files, 54k lines of test code — and none of it executes automatically.

2. **~84% of tests are unrunnable without credentials.** They're useful for local developer validation but provide zero automated safety net.

3. **Only ~14 integrations have mocked tests** that could run in CI today without any secrets. These are the low-hanging fruit for CI integration.

4. **Two competing test "philosophies" coexist:**
   - SDK template approach: manual script, print output, eyeball it
   - Modern approach: pytest + mocks + assertions + CI-runnable

5. **No shared test utilities.** Each integration reinvents mocking patterns. There's no shared `conftest.py`, mock factory, or test helper library.

6. **Custom test runners** (slider, doc-maker) should be migrated to pytest for consistency.

7. **The largest test files are manual runners** — microsoft365 (2,349 lines), linkedin (1,413 lines), coda (1,213 lines) — all require real credentials.

---

## Recommendations (Not Actioned)

1. **Add a CI step to run pytest on mocked tests** — the 14 integrations with mocks could be validated today with zero infrastructure changes.

2. **Create a shared testing pattern** — a repo-level `conftest.py` or test utilities module with reusable mock context factories.

3. **Gradually add mocked unit tests** to integrations, especially for:
   - Error handling paths
   - Input validation
   - Data transformation logic
   - Config↔handler sync verification

4. **Standardize on pytest** — the SDK template doesn't mandate it, but pytest is already used by the most mature tests and is the Python community standard.

5. **Consider a "test tier" system:**
   - **Tier 1 (CI):** Mocked unit tests — run on every PR
   - **Tier 2 (Scheduled):** Integration tests with test-environment credentials — run nightly
   - **Tier 3 (Manual):** Full API tests with production-like credentials — run before releases

6. **Fix `Integration.load()` across all integrations** — all 86 integrations call `Integration.load()` with no arguments. The SDK resolves `config.json` relative to its own package location, which only works when the SDK is vendored into `dependencies/`. When the SDK is installed as a site-package (the test setup), this breaks. The current workaround is a monkeypatch in the root `conftest.py` that uses frame inspection to find the caller's directory. The proper fix: update all integration source files to pass an explicit path:
   ```python
   # Before (fragile)
   my_integration = Integration.load()

   # After (robust)
   import os
   my_integration = Integration.load(os.path.join(os.path.dirname(__file__), "config.json"))
   ```
   This is a bulk change across 86 files but is mechanical and safe. Once done, the monkeypatch in `conftest.py` can be removed. Consider also proposing a fix upstream in the SDK to use caller frame inspection as the default.
