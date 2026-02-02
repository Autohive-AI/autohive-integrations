# -*- coding: utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dependencies")))

from linkedin import linkedin  # noqa: F401 - re-exported for test imports
import linkedin as linkedin_module  # noqa: F401 - for mocking post_to_linkedin
