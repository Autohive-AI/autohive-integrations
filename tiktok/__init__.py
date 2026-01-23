"""
TikTok Integration for Autohive

Enables video posting, user profile management, and content analytics
via the official TikTok Content Posting API.
"""

from .tiktok import tiktok, TikTokAPIError

__all__ = ["tiktok", "TikTokAPIError"]
