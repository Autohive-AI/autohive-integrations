# Test suite for Canva integration
import asyncio
from context import canva
from autohive_integrations_sdk import ExecutionContext

# Test configuration
# IMPORTANT: Replace with your actual Canva OAuth credentials
TEST_AUTH = {
    "credentials": {
        "access_token": "your_access_token_here"
    }
}

# Store IDs for dependent tests
test_asset_id = None
test_design_id = None
test_folder_id = None
test_upload_job_id = None
test_export_job_id = None


async def test_get_user_capabilities():
    """Test getting user capabilities. FREE - helps determine what actions user can perform."""
    print("\n[TEST] Getting user capabilities...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("get_user_capabilities", inputs, context)

            if result.data.get('result'):
                capabilities = result.data.get('capabilities', [])
                print(f"✓ Found {len(capabilities)} capabilities")

                # Show key capabilities
                if capabilities:
                    for cap in capabilities[:5]:
                        print(f"  - {cap}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_design():
    """Test creating a new design."""
    print("\n[TEST] Creating a new presentation design...")

    inputs = {
        "preset_type": "presentation",
        "title": "Test Presentation from Integration"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("create_design", inputs, context)

            if result.data.get('result'):
                design = result.data.get('design', {})
                global test_design_id
                test_design_id = design.get('id')

                print(f"✓ Created design: {design.get('title')}")
                print(f"  ID: {test_design_id}")
                print(f"  Edit URL: {design.get('urls', {}).get('edit_url', 'N/A')[:60]}...")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_designs():
    """Test listing user's designs."""
    print("\n[TEST] Listing user's designs...")

    inputs = {
        "sort_by": "modified_descending"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("list_designs", inputs, context)

            if result.data.get('result'):
                designs = result.data.get('designs', [])
                print(f"✓ Found {len(designs)} design(s)")

                if designs:
                    global test_design_id
                    if not test_design_id:
                        test_design_id = designs[0].get('id')

                    # Show first few designs
                    for i, design in enumerate(designs[:3]):
                        print(f"  - {design.get('title', 'Untitled')} (ID: {design.get('id')})")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_design():
    """Test getting design metadata."""
    if not test_design_id:
        print("\n[TEST] Skipping get_design - no design_id available")
        return None

    print(f"\n[TEST] Getting design details for {test_design_id}...")

    inputs = {
        "design_id": test_design_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("get_design", inputs, context)

            if result.data.get('result'):
                design = result.data.get('design', {})
                print(f"✓ Retrieved design: {design.get('title')}")
                print(f"  Created: {design.get('created_at')}")
                print(f"  Updated: {design.get('updated_at')}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_upload_asset():
    """Test uploading an asset. This creates an actual asset."""
    print("\n[TEST] Uploading a test image asset...")
    print("  NOTE: This will create an asset in your Canva account")

    # Simple 1x1 red pixel PNG
    import base64
    png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    inputs = {
        "file": {
            "content": png_base64,
            "name": "test_image.png",
            "contentType": "image/png"
        }
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("upload_asset", inputs, context)

            if result.data.get('result'):
                global test_upload_job_id
                test_upload_job_id = result.data.get('job_id')

                print(f"✓ Upload initiated")
                print(f"  Job ID: {test_upload_job_id}")
                print(f"  Status: {result.data.get('status')}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_asset_upload_status():
    """Test checking asset upload status."""
    if not test_upload_job_id:
        print("\n[TEST] Skipping get_asset_upload_status - no upload job_id available")
        return None

    print(f"\n[TEST] Checking upload status for job {test_upload_job_id}...")

    inputs = {
        "job_id": test_upload_job_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("get_asset_upload_status", inputs, context)

            if result.data.get('result'):
                status = result.data.get('status')
                print(f"✓ Upload status: {status}")

                if status == 'success':
                    asset = result.data.get('asset', {})
                    global test_asset_id
                    test_asset_id = asset.get('id')
                    print(f"  Asset ID: {test_asset_id}")
                    print(f"  Asset Name: {asset.get('name')}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_folder():
    """Test creating a folder."""
    print("\n[TEST] Creating a test folder...")

    inputs = {
        "name": "Test Folder from Integration",
        "parent_folder_id": "root"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("create_folder", inputs, context)

            if result.data.get('result'):
                folder = result.data.get('folder', {})
                global test_folder_id
                test_folder_id = folder.get('id')

                print(f"✓ Created folder: {folder.get('name')}")
                print(f"  ID: {test_folder_id}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_folder_items():
    """Test listing folder items."""
    if not test_folder_id:
        print("\n[TEST] Skipping list_folder_items - no folder_id available")
        return None

    print(f"\n[TEST] Listing items in folder {test_folder_id}...")

    inputs = {
        "folder_id": test_folder_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("list_folder_items", inputs, context)

            if result.data.get('result'):
                items = result.data.get('items', [])
                print(f"✓ Found {len(items)} item(s)")

                if items:
                    for item in items[:5]:
                        print(f"  - {item.get('name')} ({item.get('type')})")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_export_design():
    """Test exporting a design. This creates an export job."""
    if not test_design_id:
        print("\n[TEST] Skipping export_design - no design_id available")
        return None

    print(f"\n[TEST] Exporting design {test_design_id} to PDF...")

    inputs = {
        "design_id": test_design_id,
        "format": "pdf"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("export_design", inputs, context)

            if result.data.get('result'):
                global test_export_job_id
                test_export_job_id = result.data.get('job_id')

                print(f"✓ Export initiated")
                print(f"  Job ID: {test_export_job_id}")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_export_status():
    """Test checking export status."""
    if not test_export_job_id:
        print("\n[TEST] Skipping get_export_status - no export job_id available")
        return None

    print(f"\n[TEST] Checking export status for job {test_export_job_id}...")

    inputs = {
        "export_id": test_export_job_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await canva.execute_action("get_export_status", inputs, context)

            if result.data.get('result'):
                status = result.data.get('status')
                print(f"✓ Export status: {status}")

                if status == 'success':
                    urls = result.data.get('urls', [])
                    print(f"  Download URLs: {len(urls)}")
                    if urls:
                        print(f"  First URL: {urls[0][:60]}...")

                return result
            else:
                print(f"✗ Error: {result.data.get('error')}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def main():
    print("=" * 70)
    print("Canva Integration Test Suite")
    print("=" * 70)
    print("\n📝 SETUP INSTRUCTIONS:")
    print("1. Get OAuth access token from Canva Developer Portal")
    print("2. Replace 'your_access_token_here' in TEST_AUTH with actual token")
    print("3. Ensure you have required scopes: asset:write, design:content:write, etc.")
    print("4. Note: Some tests create actual resources in your Canva account")
    print("\n" + "=" * 70)

    try:
        # Test user capabilities
        print("\n" + "=" * 70)
        print("USER CAPABILITIES (1 action)")
        print("=" * 70)
        await test_get_user_capabilities()

        # Test design management
        print("\n" + "=" * 70)
        print("DESIGN MANAGEMENT (3 actions)")
        print("=" * 70)
        await test_create_design()
        await test_list_designs()
        await test_get_design()

        # Test asset management
        print("\n" + "=" * 70)
        print("ASSET MANAGEMENT (2 actions)")
        print("=" * 70)
        await test_upload_asset()

        # Wait a bit for upload to process
        if test_upload_job_id:
            print("\n⏳ Waiting 3 seconds for upload to process...")
            await asyncio.sleep(3)

        await test_get_asset_upload_status()

        # Test folder management
        print("\n" + "=" * 70)
        print("FOLDER MANAGEMENT (2 actions)")
        print("=" * 70)
        await test_create_folder()
        await test_list_folder_items()

        # Test export
        print("\n" + "=" * 70)
        print("DESIGN EXPORT (2 actions)")
        print("=" * 70)
        await test_export_design()

        # Wait a bit for export to process
        if test_export_job_id:
            print("\n⏳ Waiting 5 seconds for export to process...")
            await asyncio.sleep(5)

        await test_get_export_status()

        print("\n" + "=" * 70)
        print("✓ Test suite completed!")
        print("=" * 70)
        print("\n📊 Summary: 10 actions tested")
        print("  - User: get_user_capabilities")
        print("  - Designs: create_design, list_designs, get_design")
        print("  - Assets: upload_asset, get_asset_upload_status")
        print("  - Folders: create_folder, list_folder_items")
        print("  - Export: export_design, get_export_status")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
