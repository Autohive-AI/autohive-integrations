# -*- coding: utf-8 -*-
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, "dependencies"))

# Import using importlib to avoid conflict with 'stripe' package
import importlib.util
spec = importlib.util.spec_from_file_location("stripe_module", os.path.join(parent_dir, "stripe.py"))
stripe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stripe_module)
stripe_integration = stripe_module.stripe
