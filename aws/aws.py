from autohive_integrations_sdk import Integration
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
integration = Integration.load(config_path)

# Import actions to register handlers
import actions
