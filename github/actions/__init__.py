"""
GitHub integration actions.

Importing this package registers every action handler with the integration
instance, as a side effect of importing each module below.

Handler registration is verified by tests/test_github_config_unit.py, which
asserts that the registered handlers exactly match config.json's actions — so a
module missing from this list fails the test suite rather than silently
dropping actions.
"""

from . import branches
from . import commits
from . import files
from . import gists
from . import issues
from . import labels
from . import misc
from . import pr_reviews
from . import prs
from . import releases
from . import repos
from . import search
from . import security
from . import sub_issues
from . import users_orgs
from . import webhooks
from . import workflows

__all__ = [
    "branches",
    "commits",
    "files",
    "gists",
    "issues",
    "labels",
    "misc",
    "pr_reviews",
    "prs",
    "releases",
    "repos",
    "search",
    "security",
    "sub_issues",
    "users_orgs",
    "webhooks",
    "workflows",
]
