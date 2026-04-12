from autohive_integrations_sdk import Integration


aws = Integration.load()

# Import actions to register handlers
import actions  # noqa: F401, E402
