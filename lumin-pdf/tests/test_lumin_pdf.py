import asyncio
import os
import sys
from context import lumin_pdf
from autohive_integrations_sdk import ExecutionContext

ACCESS_TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("LUMIN_PDF_TOKEN", "")
TEST_AUTH = {"api_key": ACCESS_TOKEN}  # nosec B105


# ---- User & Workspace ----


async def test_get_current_user():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action("get_current_user", {}, context)
            print(f"Get Current User: {result}")
            assert result.result.data.get("result")
            assert "user" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_workspace():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action("get_workspace", {}, context)
            print(f"Get Workspace: {result}")
            assert result.result.data.get("result")
            assert "workspace" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_workspace_members():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action("list_workspace_members", {"limit": 10}, context)
            print(f"List Workspace Members: {result}")
            assert result.result.data.get("result")
            assert "members" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# ---- Templates ----


async def test_list_templates():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, context)
            print(f"List Templates: {result}")
            assert result.result.data.get("result")
            assert "templates" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_template(template_id: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action("get_template", {"template_id": template_id}, context)
            print(f"Get Template: {result}")
            assert result.result.data.get("result")
            assert "template" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# ---- Signature Requests ----


async def test_send_signature_request(file_url: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            inputs = {
                "title": "Test Signature Request",
                "file_url": file_url,
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
                "message": "Please sign this test document.",
            }
            result = await lumin_pdf.execute_action("send_signature_request", inputs, context)
            print(f"Send Signature Request: {result}")
            assert result.result.data.get("result")
            assert "signature_request" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_signature_request(sig_req_id: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action(
                "get_signature_request", {"signature_request_id": sig_req_id}, context
            )
            print(f"Get Signature Request: {result}")
            assert result.result.data.get("result")
            assert "signature_request" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_generate_signing_link(sig_req_id: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            inputs = {
                "signature_request_id": sig_req_id,
                "signer_email": "engineering@autohive.com",
            }
            result = await lumin_pdf.execute_action("generate_signing_link", inputs, context)
            print(f"Generate Signing Link: {result}")
            assert result.result.data.get("result")
            assert "signing_link" in result.result.data
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_send_reminder(sig_req_id: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            inputs = {
                "signature_request_id": sig_req_id,
                "emails": ["engineering@autohive.com"],
            }
            result = await lumin_pdf.execute_action("send_reminder", inputs, context)
            print(f"Send Reminder: {result}")
            assert result.result.data.get("result")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_cancel_signature_request(sig_req_id: str):
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await lumin_pdf.execute_action(
                "cancel_signature_request",
                {"signature_request_id": sig_req_id},
                context,
            )
            print(f"Cancel Signature Request: {result}")
            assert result.result.data.get("result")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


def _extract(result, *keys):
    """Safely dig a value out of a result's data dict."""
    if result is None:
        return None
    data = result.result.data
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


async def run_all_tests():
    print("=" * 60)
    print("Lumin PDF Integration Test Suite")
    print("=" * 60)

    results = []

    def record(name, result):
        results.append((name, result is not None))
        return result

    # --- Read-only tests ---
    print(f"\n{'-' * 60}\nRunning: Get Current User\n{'-' * 60}")
    record("Get Current User", await test_get_current_user())

    print(f"\n{'-' * 60}\nRunning: Get Workspace\n{'-' * 60}")
    record("Get Workspace", await test_get_workspace())

    print(f"\n{'-' * 60}\nRunning: List Workspace Members\n{'-' * 60}")
    record("List Workspace Members", await test_list_workspace_members())

    print(f"\n{'-' * 60}\nRunning: List Templates\n{'-' * 60}")
    list_tpl_result = await test_list_templates()
    record("List Templates", list_tpl_result)

    # --- Template tests (skip if no templates exist) ---
    templates = _extract(list_tpl_result, "templates") or []
    template_id = templates[0].get("id") if templates else None

    if template_id:
        print(f"\n{'-' * 60}\nRunning: Get Template (id={template_id})\n{'-' * 60}")
        record("Get Template", await test_get_template(template_id))
    else:
        print("\nSkipping Get Template — no templates in workspace")
        results.append(("Get Template", None))

    PDF_URL = "https://www.learningcontainer.com/wp-content/uploads/2019/09/sample-pdf-file.pdf"

    # --- Signature request chain ---
    sig_req_id = None
    print(f"\n{'-' * 60}\nRunning: Send Signature Request\n{'-' * 60}")
    sr_result = await test_send_signature_request(PDF_URL)
    record("Send Signature Request", sr_result)
    if sr_result is not None:
        sr_data = _extract(sr_result, "signature_request")
        if isinstance(sr_data, dict):
            sig_req_id = sr_data.get("id") or sr_data.get("signature_request_id")
            if sig_req_id is None and isinstance(sr_data.get("signature_request"), dict):
                nested = sr_data["signature_request"]
                sig_req_id = nested.get("id") or nested.get("signature_request_id")

    if sig_req_id:
        print(f"\n{'-' * 60}\nRunning: Get Signature Request (id={sig_req_id})\n{'-' * 60}")
        record("Get Signature Request", await test_get_signature_request(sig_req_id))

        print(f"\n{'-' * 60}\nRunning: Generate Signing Link (id={sig_req_id})\n{'-' * 60}")
        record("Generate Signing Link", await test_generate_signing_link(sig_req_id))

        print(f"\n{'-' * 60}\nRunning: Send Reminder (id={sig_req_id})\n{'-' * 60}")
        record("Send Reminder", await test_send_reminder(sig_req_id))

        print(f"\n{'-' * 60}\nRunning: Cancel Signature Request (id={sig_req_id})\n{'-' * 60}")
        record("Cancel Signature Request", await test_cancel_signature_request(sig_req_id))
    else:
        print("\nSkipping signature request sub-tests — no signature_request id")
        for name in (
            "Get Signature Request",
            "Generate Signing Link",
            "Send Reminder",
            "Download Signed Document",
            "Cancel Signature Request",
        ):
            results.append((name, None))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        if passed is None:
            status = "SKIP"
        elif passed:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    skipped_count = sum(1 for _, passed in results if passed is None)
    total = len(results)
    print(f"\nTotal: {passed_count}/{total - skipped_count} tests passed ({skipped_count} skipped)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
