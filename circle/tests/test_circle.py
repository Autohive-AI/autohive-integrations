# Test for Circle.so community platform integration
import asyncio
from context import circle
from autohive_integrations_sdk import ExecutionContext

# Test configuration - update these with your actual test data
TEST_API_TOKEN = "your-circle-api-token-here"  # Replace with actual token
TEST_SPACE_ID = 12345  # Replace with an actual space ID from your Circle community
TEST_POST_ID = "test-post-id"  # Replace with an actual post ID
TEST_MEMBER_EMAIL = "test@example.com"  # Replace with an actual member email
TEST_MEMBER_ID = "test-member-id"  # Replace with an actual member ID


async def test_get_community_info():
    """
    Test the get_community_info action to retrieve community details
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_community_info", inputs, context)
            if result.result.data.get('result'):
                community = result.result.data.get('community', {})
                print(f"V Success: Retrieved community info")
                print(f"  Community Name: {community.get('name')}")
                print(f"  Community ID: {community.get('id')}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_community_info: {str(e)}")
            return None


async def test_search_spaces():
    """
    Test the search_spaces action to find spaces in the community
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("search_spaces", inputs, context)
            if result.result.data.get('result'):
                spaces = result.result.data.get('spaces', [])
                count = result.result.data.get('count', 0)
                print(f"V Success: Retrieved {count} spaces")
                for space in spaces[:3]:  # Show first 3
                    print(f"  - Space: {space.get('name')} (ID: {space.get('id')}, Type: {space.get('space_type')})")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing search_spaces: {str(e)}")
            return None


async def test_get_space():
    """
    Test the get_space action to retrieve details of a specific space
    """
    # First get available spaces
    spaces_result = await test_search_spaces()
    if not spaces_result or not spaces_result.result.data.get('spaces'):
        print("Cannot test get_space without space information")
        return

    # Use the first available space
    space_id = spaces_result.result.data['spaces'][0]['id']
    print(f"\nUsing space ID: {space_id}")

    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "space_id": str(space_id)
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_space", inputs, context)
            if result.result.data.get('result'):
                space = result.result.data.get('space', {})
                print(f"V Success: Retrieved space details")
                print(f"  Name: {space.get('name')}")
                print(f"  Type: {space.get('space_type')}")
                print(f"  Members: {space.get('members_count', 0)}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_space: {str(e)}")
            return None


async def test_search_posts():
    """
    Test the search_posts action to find posts in the community
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "status": "published",
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("search_posts", inputs, context)
            if result.result.data.get('result'):
                posts = result.result.data.get('posts', [])
                count = result.result.data.get('count', 0)
                print(f"V Success: Retrieved {count} posts")
                for post in posts[:3]:  # Show first 3
                    print(f"  - Post: {post.get('name')} (ID: {post.get('id')}, Status: {post.get('status')})")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing search_posts: {str(e)}")
            return None


async def test_get_post():
    """
    Test the get_post action to retrieve details of a specific post
    """
    # First get available posts
    posts_result = await test_search_posts()
    if not posts_result or not posts_result.result.data.get('posts'):
        print("Cannot test get_post without post information")
        return

    # Use the first available post
    post_id = posts_result.result.data['posts'][0]['id']
    print(f"\nUsing post ID: {post_id}")

    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "post_id": str(post_id)
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_post", inputs, context)
            if result.result.data.get('result'):
                post = result.result.data.get('post', {})
                print(f"V Success: Retrieved post details")
                print(f"  Title: {post.get('name')}")
                print(f"  Status: {post.get('status')}")
                print(f"  Comments: {post.get('comments_count', 0)}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_post: {str(e)}")
            return None


async def test_create_post_with_markdown():
    """
    Test the create_post action with markdown formatting
    """
    # First get available spaces
    spaces_result = await test_search_spaces()
    if not spaces_result or not spaces_result.data.get('spaces'):
        print("Cannot test create_post without space information")
        return

    # Use the first available space
    space_id = spaces_result.data['spaces'][0]['id']
    print(f"\nCreating post in space ID: {space_id}")

    auth = {
        "credentials": {
            "api_token": "your-circle-api-token-here"
        }
    }

    inputs = {
        "space_id": space_id,
        "name": "Test Post - Autohive Integration",
        "body": """
# Test Post

This is a test post created by the Autohive Circle integration.

## Features Tested

- **Bold text** formatting
- *Italic text* formatting
- ~~Strikethrough~~ text
- `Code inline` formatting

### List Items

1. First item
2. Second item
3. Third item

- Bullet point one
- Bullet point two

> This is a blockquote for testing

```python
# Code block example
def hello_world():
    print("Hello from Circle!")
```

[Link to Circle](https://circle.so)
        """,
        "status": "draft",  # Create as draft to avoid cluttering the community
        "is_comments_enabled": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("create_post", inputs, context)
            if result.data.get('result'):
                post = result.data.get('post', {})
                print(f"V Success: Created post")
                print(f"  Post ID: {post.get('id')}")
                print(f"  Title: {post.get('name')}")
                print(f"  Status: {post.get('status')}")
            else:
                print(f"X Error: {result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing create_post: {str(e)}")
            return None


async def test_update_post():
    """
    Test the update_post action to modify an existing post
    Note: This requires a valid post ID
    """
    auth = {
        "credentials": {
            "api_token": "your-circle-api-token-here"
        }
    }

    inputs = {
        "post_id": TEST_POST_ID,  # Replace with actual post ID
        "name": "Updated Test Post Title",
        "is_pinned": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("update_post", inputs, context)
            if result.data.get('result'):
                post = result.data.get('post', {})
                print(f"V Success: Updated post")
                print(f"  Title: {post.get('name')}")
                print(f"  Pinned: {post.get('is_pinned')}")
            else:
                print(f"X Error: {result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing update_post: {str(e)}")
            return None


async def test_list_members():
    """
    Test the list_members action to retrieve community members
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("list_members", inputs, context)
            if result.result.data.get('result'):
                members = result.result.data.get('members', [])
                count = result.result.data.get('count', 0)
                print(f"V Success: Retrieved {count} members")
                for member in members[:3]:  # Show first 3
                    print(f"  - Member: {member.get('name')} ({member.get('email')})")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing list_members: {str(e)}")
            return None


async def test_search_member_by_email():
    """
    Test the search_member_by_email action
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "email": TEST_MEMBER_EMAIL  # Replace with actual member email
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("search_member_by_email", inputs, context)
            if result.result.data.get('result'):
                member = result.result.data.get('member', {})
                print(f"V Success: Found member")
                print(f"  Name: {member.get('name')}")
                print(f"  Email: {member.get('email')}")
                print(f"  Member ID: {member.get('id')}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing search_member_by_email: {str(e)}")
            return None


async def test_get_member():
    """
    Test the get_member action to retrieve member details
    """
    # First get members list
    members_result = await test_list_members()
    if not members_result or not members_result.result.data.get('members'):
        print("Cannot test get_member without member information")
        return

    # Use the first available member
    member_id = members_result.result.data['members'][0]['id']
    print(f"\nUsing member ID: {member_id}")

    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "member_id": str(member_id)
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_member", inputs, context)
            if result.result.data.get('result'):
                member = result.result.data.get('member', {})
                print(f"V Success: Retrieved member details")
                print(f"  Name: {member.get('name')}")
                print(f"  Email: {member.get('email')}")
                print(f"  Status: {member.get('status')}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_member: {str(e)}")
            return None


async def test_search_events():
    """
    Test the search_events action to find upcoming events
    """
    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "time_filter": "upcoming",
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("search_events", inputs, context)
            if result.result.data.get('result'):
                events = result.result.data.get('events', [])
                count = result.result.data.get('count', 0)
                print(f"V Success: Retrieved {count} upcoming events")
                for event in events[:3]:  # Show first 3
                    name = event.get('name', 'Unknown')
                    # Sanitize name for printing to console
                    safe_name = name.encode('ascii', 'ignore').decode('ascii')
                    print(f"  - Event: {safe_name} (Start: {event.get('start_date')})")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing search_events: {str(e)}")
            return None


async def test_get_event():
    """
    Test the get_event action to retrieve event details
    """
    # First get available events
    events_result = await test_search_events()
    if not events_result or not events_result.result.data.get('events'):
        print("Cannot test get_event without event information")
        return

    # Use the first available event
    event_id = events_result.result.data['events'][0]['id']
    print(f"\nUsing event ID: {event_id}")

    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "event_id": str(event_id)
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_event", inputs, context)
            if result.result.data.get('result'):
                event = result.result.data.get('event', {})
                print(f"V Success: Retrieved event details")
                name = event.get('name', 'Unknown')
                safe_name = name.encode('ascii', 'ignore').decode('ascii')
                print(f"  Name: {safe_name}")
                print(f"  Start: {event.get('start_date')}")
                print(f"  Location: {event.get('location')}")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_event: {str(e)}")
            return None


async def test_create_comment():
    """
    Test the create_comment action to add a comment to a post
    """
    # First get available posts
    posts_result = await test_search_posts()
    if not posts_result or not posts_result.data.get('posts'):
        print("Cannot test create_comment without post information")
        return

    # Use the first available post
    post_id = posts_result.data['posts'][0]['id']
    print(f"\nAdding comment to post ID: {post_id}")

    auth = {
        "credentials": {
            "api_token": "your-circle-api-token-here"
        }
    }

    inputs = {
        "post_id": str(post_id),
        "body": "This is a test comment from the Autohive Circle integration!"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("create_comment", inputs, context)
            if result.data.get('result'):
                comment = result.data.get('comment', {})
                print(f"V Success: Created comment")
                print(f"  Comment ID: {comment.get('id')}")
                print(f"  Body: {comment.get('body')}")
            else:
                print(f"X Error: {result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing create_comment: {str(e)}")
            return None


async def test_get_post_comments():
    """
    Test the get_post_comments action to retrieve comments from a post
    """
    # First get available posts
    posts_result = await test_search_posts()
    if not posts_result or not posts_result.result.data.get('posts'):
        print("Cannot test get_post_comments without post information")
        return

    # Use the first available post
    post_id = posts_result.result.data['posts'][0]['id']
    print(f"\nGetting comments for post ID: {post_id}")

    auth = {
        "credentials": {
            "api_token": TEST_API_TOKEN
        }
    }

    inputs = {
        "post_id": str(post_id),
        "per_page": 20
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await circle.execute_action("get_post_comments", inputs, context)
            if result.result.data.get('result'):
                comments = result.result.data.get('comments', [])
                count = result.result.data.get('count', 0)
                print(f"V Success: Retrieved {count} comments")
                for comment in comments[:3]:  # Show first 3
                    print(f"  - Comment: {comment.get('body')[:50]}...")
            else:
                print(f"X Error: {result.result.data.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            print(f"X Exception testing get_post_comments: {str(e)}")
            return None


async def main():
    """
    Run all Circle integration tests
    """
    print("=" * 60)
    print("Testing Circle Integration")
    print("=" * 60)
    print("\nNote: Update the API token in each test before running!")
    print("=" * 60)

    # Basic tests - these don't modify data
    print("\n[1/15] Testing get_community_info...")
    await test_get_community_info()

    print("\n[2/15] Testing search_spaces...")
    await test_search_spaces()

    print("\n[3/15] Testing get_space...")
    await test_get_space()

    print("\n[4/15] Testing search_posts...")
    await test_search_posts()

    print("\n[5/15] Testing get_post...")
    await test_get_post()

    print("\n[6/15] Testing list_members...")
    await test_list_members()

    print("\n[7/15] Testing get_member...")
    await test_get_member()

    print("\n[8/15] Testing search_events...")
    await test_search_events()

    print("\n[9/15] Testing get_event...")
    await test_get_event()

    print("\n[10/15] Testing get_post_comments...")
    await test_get_post_comments()

    # Tests that modify data - uncomment when ready to test
    # print("\n[11/15] Testing create_post_with_markdown...")
    # await test_create_post_with_markdown()

    # print("\n[12/15] Testing update_post...")
    # await test_update_post()

    # print("\n[13/15] Testing search_member_by_email...")
    # await test_search_member_by_email()

    # print("\n[14/15] Testing create_comment...")
    # await test_create_comment()

    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
