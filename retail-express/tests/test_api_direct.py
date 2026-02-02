# Direct API test for Retail Express integration
import asyncio
import aiohttp

API_KEY = "Secret"
BASE_URL = "https://api.retailexpress.com.au"
API_VERSION = "v2.1"


async def get_access_token(session):
    """Get access token from API."""
    url = f"{BASE_URL}/{API_VERSION}/auth/token"
    headers = {"x-api-key": API_KEY, "Accept": "application/json"}

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            return data.get('access_token', '')
        else:
            text = await response.text()
            raise Exception(f"Token error: {response.status} - {text}")


def get_auth_headers(access_token):
    """Build auth headers."""
    return {
        "Authorization": f"Bearer {access_token}",
        "x-api-key": API_KEY,
        "Accept": "application/json"
    }


async def test_list_products(session, token):
    url = f"{BASE_URL}/{API_VERSION}/products"
    async with session.get(url, headers=get_auth_headers(token), params={"PageSize": 3}) as r:
        return await r.json() if r.status == 200 else {"error": r.status}


async def test_list_customers(session, token):
    url = f"{BASE_URL}/{API_VERSION}/customers"
    async with session.get(url, headers=get_auth_headers(token), params={"PageSize": 3}) as r:
        return await r.json() if r.status == 200 else {"error": r.status}


async def test_list_orders(session, token):
    url = f"{BASE_URL}/{API_VERSION}/orders"
    async with session.get(url, headers=get_auth_headers(token), params={"PageSize": 3}) as r:
        return await r.json() if r.status == 200 else {"error": r.status}


async def test_list_outlets(session, token):
    url = f"{BASE_URL}/{API_VERSION}/outlets"
    async with session.get(url, headers=get_auth_headers(token), params={"PageSize": 3}) as r:
        return await r.json() if r.status == 200 else {"error": r.status}


async def main():
    print("=" * 50)
    print("Retail Express API Tests")
    print("=" * 50)

    async with aiohttp.ClientSession() as session:
        # Get token
        print("\n1. Getting access token...")
        try:
            token = await get_access_token(session)
            print("   [PASS] Token obtained")
        except Exception as e:
            print(f"   [FAIL] {e}")
            return

        # Test list_products
        print("\n2. Testing list_products...")
        try:
            result = await test_list_products(session, token)
            if "error" not in result:
                count = len(result) if isinstance(result, list) else len(result.get('Data', []))
                print(f"   [PASS] Got {count} products")
            else:
                print(f"   [FAIL] {result}")
        except Exception as e:
            print(f"   [FAIL] {e}")

        # Test list_customers
        print("\n3. Testing list_customers...")
        try:
            result = await test_list_customers(session, token)
            if "error" not in result:
                count = len(result) if isinstance(result, list) else len(result.get('Data', []))
                print(f"   [PASS] Got {count} customers")
            else:
                print(f"   [FAIL] {result}")
        except Exception as e:
            print(f"   [FAIL] {e}")

        # Test list_orders
        print("\n4. Testing list_orders...")
        try:
            result = await test_list_orders(session, token)
            if "error" not in result:
                count = len(result) if isinstance(result, list) else len(result.get('Data', []))
                print(f"   [PASS] Got {count} orders")
            else:
                print(f"   [FAIL] {result}")
        except Exception as e:
            print(f"   [FAIL] {e}")

        # Test list_outlets
        print("\n5. Testing list_outlets...")
        try:
            result = await test_list_outlets(session, token)
            if "error" not in result:
                count = len(result) if isinstance(result, list) else len(result.get('Data', []))
                print(f"   [PASS] Got {count} outlets")
            else:
                print(f"   [FAIL] {result}")
        except Exception as e:
            print(f"   [FAIL] {e}")

    print("\n" + "=" * 50)
    print("Tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
