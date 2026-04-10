# -*- coding: utf-8 -*-
"""
Test context setup for Shopify Storefront API integration.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shopify_storefront import shopify_storefront

__all__ = ['shopify_storefront']
