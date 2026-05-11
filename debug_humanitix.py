import asyncio
import os
import sys
import importlib.util

os.chdir(os.path.join(os.path.dirname(__file__), "humanitix"))
sys.path.insert(0, ".")

spec = importlib.util.spec_from_file_location("humanitix_mod", "humanitix.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["humanitix"] = mod
spec.loader.exec_module(mod)

from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse
import aiohttp

API_KEY = os.environ.get("HUMANITIX_API_KEY", "")
print("API_KEY set:", bool(API_KEY), "| length:", len(API_KEY))


async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
    print("FETCHING:", url)
    print("HEADERS:", headers)
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
            print("STATUS:", resp.status)
            try:
                data = await resp.json(content_type=None)
            except Exception as e:
                data = await resp.text()
                print("RESPONSE (text):", str(data)[:300])
            return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)


ctx = MagicMock(name="ExecutionContext")
ctx.fetch = AsyncMock(side_effect=real_fetch)
ctx.auth = {"credentials": {"api_key": API_KEY}}


async def main():
    result = await mod.humanitix.execute_action("get_events", {"page_size": 5}, ctx)
    print("TYPE:", result.type)
    if hasattr(result.result, "message"):
        print("ERROR MESSAGE:", result.result.message)
    else:
        print("DATA:", result.result.data)


asyncio.run(main())
