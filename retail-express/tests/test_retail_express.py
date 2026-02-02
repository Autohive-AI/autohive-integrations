# Testbed for Retail Express integration
import asyncio
from context import retail_express
from autohive_integrations_sdk import ExecutionContext


async def test_list_products():
    """Test listing products."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "page_number": 1,
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("list_products", inputs, context)
            print(f"List Products Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_products: {e}")
            return None


async def test_get_product():
    """Test getting a specific product."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "product_id": "test_product_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("get_product", inputs, context)
            print(f"Get Product Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_product: {e}")
            return None


async def test_list_customers():
    """Test listing customers."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "page_number": 1,
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("list_customers", inputs, context)
            print(f"List Customers Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_customers: {e}")
            return None


async def test_get_customer():
    """Test getting a specific customer."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "customer_id": "test_customer_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("get_customer", inputs, context)
            print(f"Get Customer Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_customer: {e}")
            return None


async def test_create_customer():
    """Test creating a new customer."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "first_name": "Test",
        "last_name": "Customer",
        "email": "test.customer@example.com",
        "phone": "0412345678"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("create_customer", inputs, context)
            print(f"Create Customer Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_customer: {e}")
            return None


async def test_update_customer():
    """Test updating a customer."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "customer_id": "test_customer_id_here",
        "first_name": "Updated",
        "last_name": "Customer"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("update_customer", inputs, context)
            print(f"Update Customer Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_customer: {e}")
            return None


async def test_list_orders():
    """Test listing orders."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "page_number": 1,
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("list_orders", inputs, context)
            print(f"List Orders Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_orders: {e}")
            return None


async def test_get_order():
    """Test getting a specific order."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "order_id": "test_order_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("get_order", inputs, context)
            print(f"Get Order Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_order: {e}")
            return None


async def test_list_outlets():
    """Test listing outlets."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "page_number": 1,
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("list_outlets", inputs, context)
            print(f"List Outlets Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_outlets: {e}")
            return None


async def test_get_outlet():
    """Test getting a specific outlet."""
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_key": "your_api_key_here"
        }
    }

    inputs = {
        "outlet_id": "test_outlet_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await retail_express.execute_action("get_outlet", inputs, context)
            print(f"Get Outlet Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_outlet: {e}")
            return None


async def main():
    print("Testing Retail Express Integration")
    print("===================================")
    print()

    print("1. Testing list_products...")
    await test_list_products()
    print()

    print("2. Testing get_product...")
    await test_get_product()
    print()

    print("3. Testing list_customers...")
    await test_list_customers()
    print()

    print("4. Testing get_customer...")
    await test_get_customer()
    print()

    print("5. Testing create_customer...")
    await test_create_customer()
    print()

    print("6. Testing update_customer...")
    await test_update_customer()
    print()

    print("7. Testing list_orders...")
    await test_list_orders()
    print()

    print("8. Testing get_order...")
    await test_get_order()
    print()

    print("9. Testing list_outlets...")
    await test_list_outlets()
    print()

    print("10. Testing get_outlet...")
    await test_get_outlet()
    print()

    print("Testing completed!")


if __name__ == "__main__":
    asyncio.run(main())
