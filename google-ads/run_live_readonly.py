"""
Quick live test using a short-lived access token (no refresh token needed).

Usage:
    Set the variables in the CONFIG block below, then run:
        python google-ads/run_live_readonly.py
"""

import os
import sys
import asyncio
import importlib
from unittest.mock import MagicMock, AsyncMock

# ============================================================================
# CONFIG — fill these in before running
# ============================================================================
ACCESS_TOKEN = os.environ.get("GOOGLE_ADS_ACCESS_TOKEN", "")
DEVELOPER_TOKEN = os.environ.get("ADWORDS_DEVELOPER_TOKEN", "")
LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")  # MCC account ID
CUSTOMER_ID = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")  # client account ID
# ============================================================================

if not all([ACCESS_TOKEN, DEVELOPER_TOKEN, LOGIN_CUSTOMER_ID, CUSTOMER_ID]):
    print("Missing required config. Set these env vars:")
    print("  GOOGLE_ADS_ACCESS_TOKEN")
    print("  ADWORDS_DEVELOPER_TOKEN")
    print("  GOOGLE_ADS_LOGIN_CUSTOMER_ID  (MCC/manager account ID)")
    print("  GOOGLE_ADS_CUSTOMER_ID        (client account ID to query)")
    sys.exit(1)

# Make the developer token available to google_ads.py when it builds the client.
os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", DEVELOPER_TOKEN)

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__)))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

_spec = importlib.util.spec_from_file_location("google_ads_mod", os.path.join(_parent, "google_ads.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_ads = _mod.google_ads

from autohive_integrations_sdk.integration import ResultType  # noqa: E402

ctx = MagicMock(name="ExecutionContext")
ctx.fetch = AsyncMock()
ctx.auth = {
    "auth_type": "PlatformOauth2",
    "credentials": {"access_token": ACCESS_TOKEN},
}

base = {"login_customer_id": LOGIN_CUSTOMER_ID, "customer_id": CUSTOMER_ID}

PASS = "✓"  # nosec B105
FAIL = "✗"
SKIP = "—"


async def run():
    results = []

    async def check(label, coro):
        try:
            result = await coro
            if result.type == ResultType.ACTION:
                print(f"  {PASS} {label}")
                results.append((label, True, None))
                return result
            else:
                msg = getattr(result.result, "message", None) or str(result.result)
                print(f"  {FAIL} {label}: {result.type.value} — {msg[:120]}")
                results.append((label, False, msg))
                return result
        except Exception as e:
            print(f"  {FAIL} {label}: EXCEPTION — {e}")
            results.append((label, False, str(e)))
            return None

    print("\n── get_accessible_accounts ──────────────────────────────")
    r = await check(
        "returns accounts list",
        google_ads.execute_action("get_accessible_accounts", {}, ctx),
    )
    if r and r.type == ResultType.ACTION:
        accounts = r.result.data.get("accounts", [])
        print(f"     → {len(accounts)} account(s) found")
        for a in accounts[:5]:
            print(f"       • {a.get('customer_id')} — {a.get('descriptive_name')}")

    print("\n── retrieve_campaign_metrics ────────────────────────────")
    r = await check(
        "last 7 days",
        google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**base, "date_ranges": ["last 7 days"]},
            ctx,
        ),
    )
    if r and r.type == ResultType.ACTION:
        entries = r.result.data.get("results", [{}])[0].get("data", [])
        print(f"     → {len(entries)} campaign(s)")
        for c in entries[:3]:
            print(f"       • {c.get('Campaign')} — clicks: {c.get('Clicks')}, cost: {c.get('Cost')}")

    print("\n── retrieve_ad_group_metrics ────────────────────────────")
    r = await check(
        "last 7 days",
        google_ads.execute_action(
            "retrieve_ad_group_metrics",
            {**base, "date_ranges": ["last 7 days"]},
            ctx,
        ),
    )
    if r and r.type == ResultType.ACTION:
        entries = r.result.data.get("results", [{}])[0].get("data", [])
        print(f"     → {len(entries)} ad group(s)")

    print("\n── retrieve_ad_metrics ──────────────────────────────────")
    r = await check(
        "last 7 days",
        google_ads.execute_action(
            "retrieve_ad_metrics",
            {**base, "date_ranges": ["last 7 days"]},
            ctx,
        ),
    )
    if r and r.type == ResultType.ACTION:
        entries = r.result.data.get("results", [{}])[0].get("data", [])
        print(f"     → {len(entries)} ad(s)")

    print("\n── retrieve_search_terms ────────────────────────────────")
    await check(
        "last 7 days",
        google_ads.execute_action(
            "retrieve_search_terms",
            {**base, "date_ranges": ["last 7 days"]},
            ctx,
        ),
    )

    print("\n── get_active_ad_urls ───────────────────────────────────")
    r = await check(
        "all active ads",
        google_ads.execute_action("get_active_ad_urls", base, ctx),
    )
    if r and r.type == ResultType.ACTION:
        print(f"     → {r.result.data.get('total_count', 0)} active ad(s)")

    print("\n── generate_keyword_ideas ───────────────────────────────")
    r = await check(
        "seed: digital marketing",
        google_ads.execute_action(
            "generate_keyword_ideas",
            {**base, "seed_keywords": ["digital marketing"]},
            ctx,
        ),
    )
    if r and r.type == ResultType.ACTION:
        ideas = r.result.data.get("keyword_ideas", [])
        print(f"     → {len(ideas)} idea(s)")
        for i in ideas[:3]:
            comp = i.get("competition")
            print(f"       • {i.get('keyword')} — {i.get('avg_monthly_searches')} searches/mo, comp: {comp}")

    print("\n── generate_keyword_historical_metrics ──────────────────")
    r = await check(
        "keywords: [digital marketing, seo]",
        google_ads.execute_action(
            "generate_keyword_historical_metrics",
            {**base, "keywords": ["digital marketing", "seo"]},
            ctx,
        ),
    )
    if r and r.type == ResultType.ACTION:
        metrics = r.result.data.get("keyword_metrics", [])
        print(f"     → {len(metrics)} keyword(s)")
        for m in metrics[:3]:
            print(f"       • {m.get('keyword')} — avg: {m.get('avg_monthly_searches')}, comp: {m.get('competition')}")

    # Summary
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'─' * 56}")
    print(f"  {passed}/{total} passed")
    if passed < total:
        print("\n  Failures:")
        for label, ok, err in results:
            if not ok:
                print(f"    {FAIL} {label}: {err[:100] if err else 'unknown'}")
    print()


asyncio.run(run())
