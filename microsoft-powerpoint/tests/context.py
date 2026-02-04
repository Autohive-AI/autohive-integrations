# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

# Mock the SDK before importing
from unittest.mock import MagicMock

# Create mock SDK module
mock_sdk = MagicMock()
mock_sdk.Integration = MagicMock()
mock_sdk.Integration.load = MagicMock(return_value=MagicMock())
mock_sdk.ExecutionContext = MagicMock
mock_sdk.ActionHandler = object
mock_sdk.ActionResult = MagicMock

# Mock the action decorator
def mock_action(name):
    def decorator(cls):
        return cls
    return decorator

mock_sdk.Integration.load.return_value.action = mock_action

sys.modules['autohive_integrations_sdk'] = mock_sdk

from microsoft_powerpoint import (
    ListPresentationsAction,
    GetPresentationAction,
    GetSlidesAction,
    GetSlideAction,
    CreatePresentationAction,
    AddSlideAction,
    UpdateSlideAction,
    DeleteSlideAction,
    ExportPdfAction,
    GetSlideImageAction,
    odata_escape,
    validate_path,
)
