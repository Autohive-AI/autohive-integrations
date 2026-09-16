"""End-to-end tests for the Code Analysis integration.

These tests execute Python through the registered SDK action and use real
temporary-directory, stdout/stderr, and file-collection behavior. The
integration has no external service or credentials, so no environment
variables are required.

Run with:
    pytest code-analysis/tests/test_code_analysis_integration.py -m integration

Never runs in CI by default: the integration marker and file name keep it out
of the unit-test discovery profile.
"""

import base64
import os

import pytest
from autohive_integrations_sdk.integration import ResultType

from code_analysis import code_analysis

pytestmark = pytest.mark.integration


class TestExecutePythonCodeContract:
    async def test_executes_code_and_returns_generated_file_through_sdk(self, mock_context):
        result = await code_analysis.execute_action(
            "execute_python_code",
            {
                "python_code": (
                    "from pathlib import Path\n"
                    "print('analysis complete')\n"
                    "Path('report.txt').write_text('real file output')"
                )
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["result"].strip() == "analysis complete"
        assert "error" not in result.result.data
        assert len(result.result.data["files"]) == 1
        output_file = result.result.data["files"][0]
        assert output_file["name"] == "report.txt"
        assert output_file["contentType"] == "text/plain"
        assert base64.b64decode(output_file["content"]) == b"real file output"

    async def test_executes_supported_pypdf_dependency(self, mock_context):
        result = await code_analysis.execute_action(
            "execute_python_code",
            {
                "python_code": (
                    "from pypdf import PdfWriter\n"
                    "writer = PdfWriter()\n"
                    "writer.add_blank_page(width=72, height=72)\n"
                    "with open('report.pdf', 'wb') as output:\n"
                    "    writer.write(output)\n"
                    "print('pdf created')"
                )
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["result"].strip() == "pdf created"
        assert "error" not in result.result.data
        assert len(result.result.data["files"]) == 1
        output_file = result.result.data["files"][0]
        assert output_file["name"] == "report.pdf"
        assert output_file["contentType"] == "application/pdf"
        assert base64.b64decode(output_file["content"]).startswith(b"%PDF-")

    @pytest.mark.parametrize("exit_code", [0, 7, "requested stop"])
    async def test_user_exit_returns_structured_action_result(self, mock_context, exit_code):
        original_cwd = os.getcwd()
        result = await code_analysis.execute_action(
            "execute_python_code",
            {"python_code": f"print('before exit')\nraise SystemExit({exit_code!r})"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["result"].strip() == "before exit"
        assert "SystemExit" in result.result.data["error"]
        assert os.getcwd() == original_cwd

    async def test_invalid_input_is_rejected_before_execution(self, mock_context):
        result = await code_analysis.execute_action("execute_python_code", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert result.result["source"] == "input"
