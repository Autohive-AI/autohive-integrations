"""Test configuration for the Substack integration.

Shared fixtures (``mock_context``, etc.) come from the repository-root
``conftest.py``. Tests import the integration via the package path
(``from substack.substack import ...``), which resolves from the repo root
that pytest puts on ``sys.path``.

Do NOT insert the integration directory onto ``sys.path`` here: that makes
``substack.py`` importable as a top-level module and shadows the ``substack``
package, breaking the package-style imports during collection.
"""
