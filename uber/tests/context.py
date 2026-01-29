# -*- coding: utf-8 -*-
"""Test context for Uber integration tests."""
import sys
import os
from unittest.mock import MagicMock, patch

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)


class MockIntegration:
    """Mock Integration that returns the class unchanged from action decorator."""
    
    def action(self, name):
        """Return decorator that just returns the class unchanged."""
        def decorator(cls):
            return cls
        return decorator


mock_integration = MockIntegration()

with patch('autohive_integrations_sdk.Integration.load', return_value=mock_integration):
    import importlib.util
    spec = importlib.util.spec_from_file_location("uber_module", os.path.join(parent_dir, "uber.py"))
    uber_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uber_module)

GetProductsAction = uber_module.GetProductsAction
GetPriceEstimateAction = uber_module.GetPriceEstimateAction
GetTimeEstimateAction = uber_module.GetTimeEstimateAction
GetRideEstimateAction = uber_module.GetRideEstimateAction
RequestRideAction = uber_module.RequestRideAction
GetRideStatusAction = uber_module.GetRideStatusAction
GetRideMapAction = uber_module.GetRideMapAction
CancelRideAction = uber_module.CancelRideAction
GetRideReceiptAction = uber_module.GetRideReceiptAction
GetUserProfileAction = uber_module.GetUserProfileAction
GetRideHistoryAction = uber_module.GetRideHistoryAction
GetPaymentMethodsAction = uber_module.GetPaymentMethodsAction

validate_coordinates = uber_module.validate_coordinates
validate_seat_count = uber_module.validate_seat_count
validate_limit = uber_module.validate_limit
validate_offset = uber_module.validate_offset
validate_required_string = uber_module.validate_required_string
UberAPIError = uber_module.UberAPIError
