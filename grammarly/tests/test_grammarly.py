# Testbed for Grammarly integration
import asyncio
from context import grammarly
from autohive_integrations_sdk import ExecutionContext

# Configuration - Replace these placeholder values with actual values for testing
CLIENT_ID = "your_client_id_here"  # Replace with actual Grammarly Client ID
CLIENT_SECRET = "your_client_secret_here"  # Replace with actual Grammarly Client Secret

# Sample test content
SAMPLE_TEXT = """
This is a sample document for testing Grammarly's API capabilities.
The text should be at least 30 words to meet the minimum requirement for scoring.
This paragraph demonstrates basic writing that can be analyzed for quality,
engagement, correctness, delivery, and clarity metrics.
"""

async def test_writing_score_workflow():
    """Test complete writing score workflow: submit document and get results."""
    print("=== TESTING WRITING SCORE API WORKFLOW ===")

    auth = {
        "auth_type": "custom",
        "credentials": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    }

    try:
        # Step 1: Submit document for analysis
        print("1. Submitting document for writing score analysis...")
        analyze_inputs = {
            "filename": "test_document.txt",
            "file_content": SAMPLE_TEXT
        }

        async with ExecutionContext(auth=auth) as context:
            analyze_result = await grammarly.execute_action("analyze_writing_score", analyze_inputs, context)

            if analyze_result.get('result'):
                score_request_id = analyze_result.get('score_request_id')
                print(f"   ✓ Document submitted successfully (ID: {score_request_id})")
            else:
                print(f"   ✗ Failed to submit document: {analyze_result.get('error')}")
                return

        # Step 2: Get results (may need to wait for processing)
        print("2. Retrieving writing score results...")
        print("   (Note: Processing may take a few moments)")

        for attempt in range(5):
            await asyncio.sleep(2)  # Wait 2 seconds between checks

            results_inputs = {
                "score_request_id": score_request_id
            }

            async with ExecutionContext(auth=auth) as context:
                results = await grammarly.execute_action("get_writing_score_results", results_inputs, context)

                if results.get('result'):
                    status = results.get('status')
                    print(f"   Status: {status} (Attempt {attempt + 1}/5)")

                    if status == "COMPLETED":
                        print(f"   ✓ Scoring completed!")
                        print(f"   General Score: {results.get('general_score')}")
                        print(f"   Engagement: {results.get('engagement')}")
                        print(f"   Correctness: {results.get('correctness')}")
                        print(f"   Delivery: {results.get('delivery')}")
                        print(f"   Clarity: {results.get('clarity')}")
                        break
                    elif status == "FAILED":
                        print(f"   ✗ Scoring failed")
                        break
                else:
                    print(f"   ✗ Error: {results.get('error')}")
                    break

        print("=== WRITING SCORE WORKFLOW TEST COMPLETED ===\n")

    except Exception as e:
        print(f"Error in writing score workflow: {e}\n")


async def test_ai_detection_workflow():
    """Test complete AI detection workflow: submit document and get results."""
    print("=== TESTING AI DETECTION API WORKFLOW ===")

    auth = {
        "auth_type": "custom",
        "credentials": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    }

    try:
        # Step 1: Submit document for AI detection
        print("1. Submitting document for AI detection analysis...")
        analyze_inputs = {
            "filename": "ai_test_document.txt",
            "file_content": SAMPLE_TEXT
        }

        async with ExecutionContext(auth=auth) as context:
            analyze_result = await grammarly.execute_action("analyze_ai_detection", analyze_inputs, context)

            if analyze_result.get('result'):
                score_request_id = analyze_result.get('score_request_id')
                print(f"   ✓ Document submitted successfully (ID: {score_request_id})")
            else:
                print(f"   ✗ Failed to submit document: {analyze_result.get('error')}")
                return

        # Step 2: Get results
        print("2. Retrieving AI detection results...")
        print("   (Note: Processing may take a few moments)")

        for attempt in range(5):
            await asyncio.sleep(2)

            results_inputs = {
                "score_request_id": score_request_id
            }

            async with ExecutionContext(auth=auth) as context:
                results = await grammarly.execute_action("get_ai_detection_results", results_inputs, context)

                if results.get('result'):
                    status = results.get('status')
                    print(f"   Status: {status} (Attempt {attempt + 1}/5)")

                    if status == "COMPLETED":
                        print(f"   ✓ AI Detection completed!")
                        print(f"   Average Confidence: {results.get('average_confidence')}")
                        print(f"   AI Generated Percentage: {results.get('ai_generated_percentage')}%")
                        break
                    elif status == "FAILED":
                        print(f"   ✗ AI Detection failed")
                        break
                else:
                    print(f"   ✗ Error: {results.get('error')}")
                    break

        print("=== AI DETECTION WORKFLOW TEST COMPLETED ===\n")

    except Exception as e:
        print(f"Error in AI detection workflow: {e}\n")


async def test_plagiarism_detection_workflow():
    """Test complete plagiarism detection workflow: submit document and get results."""
    print("=== TESTING PLAGIARISM DETECTION API WORKFLOW ===")

    auth = {
        "auth_type": "custom",
        "credentials": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    }

    try:
        # Step 1: Submit document for plagiarism detection
        print("1. Submitting document for plagiarism detection analysis...")
        analyze_inputs = {
            "filename": "plagiarism_test_document.txt",
            "file_content": SAMPLE_TEXT
        }

        async with ExecutionContext(auth=auth) as context:
            analyze_result = await grammarly.execute_action("analyze_plagiarism_detection", analyze_inputs, context)

            if analyze_result.get('result'):
                score_request_id = analyze_result.get('score_request_id')
                print(f"   ✓ Document submitted successfully (ID: {score_request_id})")
            else:
                print(f"   ✗ Failed to submit document: {analyze_result.get('error')}")
                return

        # Step 2: Get results
        print("2. Retrieving plagiarism detection results...")
        print("   (Note: Processing may take a few moments)")

        for attempt in range(5):
            await asyncio.sleep(2)

            results_inputs = {
                "score_request_id": score_request_id
            }

            async with ExecutionContext(auth=auth) as context:
                results = await grammarly.execute_action("get_plagiarism_detection_results", results_inputs, context)

                if results.get('result'):
                    status = results.get('status')
                    print(f"   Status: {status} (Attempt {attempt + 1}/5)")

                    if status == "COMPLETED":
                        print(f"   ✓ Plagiarism Detection completed!")
                        print(f"   Originality Score: {results.get('originality_score')}")
                        print(f"   Plagiarism Percentage: {results.get('plagiarism_percentage')}%")
                        break
                    elif status == "FAILED":
                        print(f"   ✗ Plagiarism Detection failed")
                        break
                else:
                    print(f"   ✗ Error: {results.get('error')}")
                    break

        print("=== PLAGIARISM DETECTION WORKFLOW TEST COMPLETED ===\n")

    except Exception as e:
        print(f"Error in plagiarism detection workflow: {e}\n")


async def test_analytics_api():
    """Test Analytics API for user statistics."""
    print("=== TESTING ANALYTICS API ===")

    auth = {
        "auth_type": "custom",
        "credentials": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    }

    try:
        # Get current date and calculate date range
        from datetime import datetime, timedelta
        date_to = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Retrieving analytics from {date_from} to {date_to}...")

        inputs = {
            "date_from": date_from,
            "date_to": date_to,
            "limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await grammarly.execute_action("get_user_analytics", inputs, context)

            if result.get('result'):
                data = result.get('data', [])
                paging = result.get('paging', {})

                print(f"   ✓ Analytics retrieved successfully")
                print(f"   Users returned: {len(data)}")
                print(f"   Has more pages: {paging.get('has_more', False)}")

                # Show first few users
                for i, user in enumerate(data[:3]):
                    print(f"\n   User {i+1}:")
                    print(f"     Name: {user.get('name')}")
                    print(f"     Email: {user.get('email')}")
                    print(f"     Days Active: {user.get('days_active')}")
                    print(f"     Sessions: {user.get('sessions_count')}")
                    print(f"     Sessions Improved: {user.get('sessions_improved_percent')}%")
                    print(f"     AI Prompts: {user.get('prompt_count')}")
            else:
                print(f"   ✗ Failed to retrieve analytics: {result.get('error')}")

        print("\n=== ANALYTICS API TEST COMPLETED ===\n")

    except Exception as e:
        print(f"Error in analytics test: {e}\n")


async def main():
    """Run all Grammarly integration tests."""
    print("=" * 60)
    print("GRAMMARLY INTEGRATION TESTS")
    print("=" * 60)
    print()

    # Check if credentials are set
    if CLIENT_ID == "your_client_id_here" or CLIENT_SECRET == "your_client_secret_here":
        print("⚠ WARNING: Please set CLIENT_ID and CLIENT_SECRET before running tests!")
        print("Edit the test_grammarly.py file and replace the placeholder values.\n")
        return

    # Run tests
    print("Starting test suite...\n")

    # Test Writing Score API
    await test_writing_score_workflow()

    # Test AI Detection API
    await test_ai_detection_workflow()

    # Test Plagiarism Detection API
    await test_plagiarism_detection_workflow()

    # Test Analytics API
    await test_analytics_api()

    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
