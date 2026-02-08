import os
import sys
import shutil
import base64
import tempfile
import io
import contextlib
import traceback
import mimetypes
from typing import Dict, Any, List

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)

code_analysis = Integration.load()

USER_OUTPUT_SUBDIR = "user_generated_files"


@code_analysis.action("execute_python_code")
class ExecutePythonCodeAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        python_code: str = inputs.get("python_code")
        if not python_code:
            raise ValueError("python_code is a required input.")

        input_file_list: List[Dict[str, Any]] = inputs.get("files", [])

        with tempfile.TemporaryDirectory() as temp_dir:
            context.logger.info(f"Executing user code in temporary directory: {temp_dir}")

            if input_file_list:
                for file_info in input_file_list:
                    file_name = file_info.get("name")
                    file_content_b64 = file_info.get("content")
                    if file_name and file_content_b64:
                        try:
                            file_bytes = base64.b64decode(file_content_b64)
                            dest_path = os.path.join(temp_dir, file_name)
                            with open(dest_path, 'wb') as f:
                                f.write(file_bytes)
                            context.logger.info(f"Decoded and wrote input file: {file_name} to {temp_dir}")
                        except Exception as e:
                            context.logger.error(f"Failed to decode or write input file {file_name}: {e}")
                    else:
                        context.logger.warn(f"Skipping input file with missing name or content: {file_info}")

            work_dir = os.path.join(temp_dir, USER_OUTPUT_SUBDIR)
            os.makedirs(work_dir, exist_ok=True)

            for item in os.listdir(temp_dir):
                src_path = os.path.join(temp_dir, item)
                if os.path.isfile(src_path):
                    shutil.copy(src_path, os.path.join(work_dir, item))

            context.logger.info(
                "User code will be executed in '%s'. All files it creates will automatically be returned.",
                work_dir,
            )

            existing_files_snapshot = set()
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    rel_path = os.path.relpath(os.path.join(root, fname), work_dir)
                    existing_files_snapshot.add(rel_path)

            stdout_io = io.StringIO()
            stderr_io = io.StringIO()

            exec_globals = {
                "__name__": "__main__",
                "__file__": "<user_code>",
                "OUTPUT_DIR": ".",
            }

            returncode = 0
            original_cwd = os.getcwd()
            try:
                os.chdir(work_dir)

                with contextlib.redirect_stdout(stdout_io), contextlib.redirect_stderr(stderr_io):
                    exec(python_code, exec_globals)
            except Exception:
                returncode = 1
                stderr_io.write(traceback.format_exc())
            finally:
                try:
                    os.chdir(original_cwd)
                except Exception as e:
                    context.logger.error(f"Failed to restore working directory: {e}")

            stdout = stdout_io.getvalue()
            stderr = stderr_io.getvalue()

            context.logger.info(f"User script stdout:\n{stdout}")
            if stderr:
                context.logger.warn(f"User script stderr:\n{stderr}")
            context.logger.info(f"User script completed with code: {returncode}")

            output_files_for_sdk: List[Dict[str, Any]] = []
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    rel_path = os.path.relpath(os.path.join(root, fname), work_dir)
                    if rel_path in existing_files_snapshot:
                        continue

                    file_abs_path = os.path.join(root, fname)
                    try:
                        with open(file_abs_path, "rb") as f_out:
                            file_content_bytes = f_out.read()

                        content_b64 = base64.b64encode(file_content_bytes).decode("utf-8")
                        content_type, _ = mimetypes.guess_type(fname)
                        if not content_type:
                            content_type = "application/octet-stream"

                        output_files_for_sdk.append({
                            "name": rel_path,
                            "content": content_b64,
                            "contentType": content_type
                        })
                        context.logger.info(f"Processed output file: {rel_path} (type: {content_type})")
                    except Exception as e:
                        context.logger.error(f"Failed to process output file {rel_path}: {e}")

            sdk_output = {
                "result": stdout,
                "files": output_files_for_sdk
            }

            if stderr:
                sdk_output["error"] = stderr

            if returncode != 0:
                context.logger.error("User script raised an exception during execution. Traceback has been captured in output.")

            return ActionResult(data=sdk_output, cost_usd=None)
