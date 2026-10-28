import os
import sys

# Make hubspot.py importable as a top-level module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def pytest_addoption(parser):
    parser.addoption(
        "--run-hubspot-destructive",
        action="store_true",
        default=False,
        help="Allow explicitly marked destructive HubSpot tests to mutate a dedicated test account",
    )
