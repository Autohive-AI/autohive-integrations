# Testbed for Dropbox integration
import asyncio
import base64
from context import dropbox
from autohive_integrations_sdk import ExecutionContext


async def test_list_folder():
    """Test listing contents of a folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "path": "",  # Empty string for root folder
        "recursive": False,
        "include_deleted": False,
        "include_mounted_folders": True,
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("list_folder", inputs, context)
            print(f"List Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'entries' in result, "Response missing 'entries' field"
            assert 'cursor' in result, "Response missing 'cursor' field"
            assert 'has_more' in result, "Response missing 'has_more' field"
            if result.get('entries'):
                print(f"  -> Found {len(result['entries'])} item(s)")
                for entry in result['entries'][:5]:
                    print(f"     - {entry.get('name')} ({entry.get('.tag')})")
            return result
        except Exception as e:
            print(f"Error testing list_folder: {e}")
            return None


async def test_list_folder_continue():
    """Test continuing to list folder contents using a cursor."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    # First get a cursor from list_folder
    inputs = {"cursor": "your_cursor_here"}  # Replace with actual cursor from list_folder

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("list_folder_continue", inputs, context)
            print(f"List Folder Continue Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'entries' in result, "Response missing 'entries' field"
            assert 'cursor' in result, "Response missing 'cursor' field"
            return result
        except Exception as e:
            print(f"Error testing list_folder_continue: {e}")
            return None


async def test_get_metadata():
    """Test getting metadata for a file or folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "path": "/path/to/your/file_or_folder",  # Replace with actual path
        "include_deleted": False,
        "include_has_explicit_shared_members": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("get_metadata", inputs, context)
            print(f"Get Metadata Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'metadata' in result, "Response missing 'metadata' field"
            if result.get('metadata'):
                metadata = result['metadata']
                print(f"  -> Name: {metadata.get('name')}")
                print(f"  -> Type: {metadata.get('.tag')}")
                if metadata.get('size'):
                    print(f"  -> Size: {metadata.get('size')} bytes")
            return result
        except Exception as e:
            print(f"Error testing get_metadata: {e}")
            return None


async def test_get_temporary_link():
    """Test getting a temporary link to stream file content."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "path": "/path/to/your/file"  # Replace with actual file path (not folder)
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("get_temporary_link", inputs, context)
            print(f"Get Temporary Link Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'link' in result, "Response missing 'link' field"
            assert 'metadata' in result, "Response missing 'metadata' field"
            if result.get('link'):
                print(f"  -> Link: {result['link'][:80]}...")
            return result
        except Exception as e:
            print(f"Error testing get_temporary_link: {e}")
            return None


async def test_upload_file():
    """Test uploading a file to Dropbox."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    # Sample file content (base64 encoded)
    sample_content = base64.b64encode(b"Hello, this is a test file from Dropbox integration!").decode('utf-8')

    inputs = {
        "path": "/test_upload_file.txt",  # Destination path in Dropbox
        "content": sample_content,
        "mode": "add",  # add, overwrite, or update
        "autorename": True,  # Rename if file exists
        "mute": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("upload_file", inputs, context)
            print(f"Upload File Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'file' in result, "Response missing 'file' field"
            if result.get('file'):
                file_info = result['file']
                print(f"  -> Uploaded: {file_info.get('name')}")
                print(f"  -> Path: {file_info.get('path_display')}")
                print(f"  -> Size: {file_info.get('size')} bytes")
            return result
        except Exception as e:
            print(f"Error testing upload_file: {e}")
            return None


async def test_create_folder():
    """Test creating a new folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "path": "/test_folder",  # Folder path to create
        "autorename": True  # Rename if folder exists
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("create_folder", inputs, context)
            print(f"Create Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'folder' in result, "Response missing 'folder' field"
            if result.get('folder'):
                folder_info = result['folder']
                print(f"  -> Created: {folder_info.get('name')}")
                print(f"  -> Path: {folder_info.get('path_display')}")
            return result
        except Exception as e:
            print(f"Error testing create_folder: {e}")
            return None


async def test_delete():
    """Test deleting a file or folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "path": "/path/to/delete"  # Replace with path to delete
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("delete", inputs, context)
            print(f"Delete Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'metadata' in result, "Response missing 'metadata' field"
            if result.get('metadata'):
                print(f"  -> Deleted: {result['metadata'].get('name')}")
            return result
        except Exception as e:
            print(f"Error testing delete: {e}")
            return None


async def test_move():
    """Test moving a file or folder to a different location."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "from_path": "/source/path",  # Replace with source path
        "to_path": "/destination/path",  # Replace with destination path
        "autorename": False,
        "allow_ownership_transfer": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("move", inputs, context)
            print(f"Move Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'metadata' in result, "Response missing 'metadata' field"
            if result.get('metadata'):
                metadata = result['metadata']
                print(f"  -> Moved to: {metadata.get('path_display')}")
            return result
        except Exception as e:
            print(f"Error testing move: {e}")
            return None


async def test_copy():
    """Test copying a file or folder to a different location."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "from_path": "/source/path",  # Replace with source path
        "to_path": "/destination/copy/path",  # Replace with destination path
        "autorename": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await dropbox.execute_action("copy", inputs, context)
            print(f"Copy Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'metadata' in result, "Response missing 'metadata' field"
            if result.get('metadata'):
                metadata = result['metadata']
                print(f"  -> Copied to: {metadata.get('path_display')}")
            return result
        except Exception as e:
            print(f"Error testing copy: {e}")
            return None


async def main():
    print("Testing Dropbox Integration - 9 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your OAuth access token")
    print("  - Paths should start with / (e.g., /folder/file.txt)")
    print("  - Use empty string '' for root folder in list_folder")
    print()
    print("TIP: Run list_folder test first to discover your files and folders!")
    print()
    print("=" * 60)
    print()

    # Test folder listing actions (2)
    print("FOLDER LISTING ACTIONS")
    print("-" * 60)
    print("1. Testing list_folder...")
    await test_list_folder()
    print()

    print("2. Testing list_folder_continue...")
    await test_list_folder_continue()
    print()

    print("=" * 60)
    print()
    print("METADATA ACTIONS")
    print("-" * 60)

    # Test metadata actions (2)
    print("3. Testing get_metadata...")
    await test_get_metadata()
    print()

    print("4. Testing get_temporary_link...")
    await test_get_temporary_link()
    print()

    print("=" * 60)
    print()
    print("WRITE OPERATIONS")
    print("-" * 60)

    # Test write actions (5)
    print("5. Testing upload_file...")
    await test_upload_file()
    print()

    print("6. Testing create_folder...")
    await test_create_folder()
    print()

    print("7. Testing delete...")
    await test_delete()
    print()

    print("8. Testing move...")
    await test_move()
    print()

    print("9. Testing copy...")
    await test_copy()
    print()

    print("=" * 60)
    print("Testing completed - 9 actions total!")
    print("  - 2 folder listing actions (list_folder, list_folder_continue)")
    print("  - 2 metadata actions (get_metadata, get_temporary_link)")
    print("  - 5 write operations (upload_file, create_folder, delete, move, copy)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
