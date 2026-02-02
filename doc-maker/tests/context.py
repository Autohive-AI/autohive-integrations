# -*- coding: utf-8 -*-
import sys
import os

# Add paths for imports FIRST
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

# Now we can import the doc-maker module
try:
    # Import from the doc_maker module
    import importlib.util

    # Change to the integration directory before loading (so Integration.load() finds config.json)
    original_cwd = os.getcwd()
    integration_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(integration_dir)

    spec = importlib.util.spec_from_file_location("doc_maker", os.path.join(integration_dir, 'doc_maker.py'))
    doc_maker_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doc_maker_module)

    # Restore original directory
    os.chdir(original_cwd)

    # Export both the integration instance and the module (for unit tests)
    doc_maker = doc_maker_module.doc_maker
    doc_maker_functions = doc_maker_module  # For accessing utility functions in unit tests
except ImportError as e:
    print(f"Import error: {e}")
    print("Available sys.path entries:")
    for path in sys.path[:5]:  # Show first 5 paths
        print(f"  {path}")
    raise