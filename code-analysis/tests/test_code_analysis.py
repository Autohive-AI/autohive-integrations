import sys
import os
import base64
import unittest
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dependencies'))

from code_analysis import ExecutePythonCodeAction


class MockLogger:
    def info(self, msg, *args):
        pass
    
    def warn(self, msg, *args):
        pass
    
    def error(self, msg, *args):
        pass


class MockContext:
    def __init__(self):
        self.logger = MockLogger()


class TestExecutePythonCodeAction(unittest.IsolatedAsyncioTestCase):
    
    async def test_simple_print(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        inputs = {
            "python_code": "print('Hello, World!')"
        }
        
        result = await action.execute(inputs, context)
        
        self.assertEqual(result.data["result"].strip(), "Hello, World!")
        self.assertEqual(result.data["files"], [])
    
    async def test_calculation(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        inputs = {
            "python_code": "result = 2 + 2\nprint(result)"
        }
        
        result = await action.execute(inputs, context)
        
        self.assertEqual(result.data["result"].strip(), "4")
    
    async def test_file_creation(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        inputs = {
            "python_code": """
with open('output.txt', 'w') as f:
    f.write('Test content')
print('File created')
"""
        }
        
        result = await action.execute(inputs, context)
        
        self.assertEqual(result.data["result"].strip(), "File created")
        self.assertEqual(len(result.data["files"]), 1)
        self.assertEqual(result.data["files"][0]["name"], "output.txt")
        
        content = base64.b64decode(result.data["files"][0]["content"]).decode('utf-8')
        self.assertEqual(content, "Test content")
    
    async def test_input_file_processing(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        input_content = "line1\nline2\nline3"
        encoded_content = base64.b64encode(input_content.encode()).decode()
        
        inputs = {
            "python_code": """
with open('input.txt', 'r') as f:
    lines = f.readlines()
print(len(lines))
""",
            "files": [
                {
                    "name": "input.txt",
                    "content": encoded_content,
                    "contentType": "text/plain"
                }
            ]
        }
        
        result = await action.execute(inputs, context)
        
        self.assertEqual(result.data["result"].strip(), "3")
    
    async def test_error_handling(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        inputs = {
            "python_code": "raise ValueError('Test error')"
        }
        
        result = await action.execute(inputs, context)
        
        self.assertIn("error", result.data)
        self.assertIn("ValueError", result.data["error"])
        self.assertIn("Test error", result.data["error"])
    
    async def test_missing_python_code(self):
        action = ExecutePythonCodeAction()
        context = MockContext()
        
        inputs = {}
        
        with self.assertRaises(ValueError):
            await action.execute(inputs, context)


if __name__ == '__main__':
    unittest.main()
