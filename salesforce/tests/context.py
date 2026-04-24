import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
deps_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, parent_dir)
sys.path.insert(0, deps_dir)
from salesforce import salesforce  # noqa
