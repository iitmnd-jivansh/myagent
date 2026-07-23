"""
Supabase client module for MyAgent.

Provides a singleton Supabase client that is configured via environment variables.
Falls back gracefully if Supabase is not configured (returns None).
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_SUPABASE_CLIENT = None


def get_supabase():
    """
    Get the Supabase client singleton.

    Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from environment.
    Returns None if either is missing (signals SQLite fallback).

    Returns:
        SupabaseClient or None
    """
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is not None:
        return _SUPABASE_CLIENT

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("[SUPABASE] Not configured (SUPABASE_URL or SUPABASE_SERVICE_KEY missing) — using SQLite fallback")
        return None

    try:
        from supabase import create_client

        _SUPABASE_CLIENT = create_client(url, key)
        print(f"[SUPABASE] Client initialized at {url}")
        return _SUPABASE_CLIENT
    except Exception as e:
        print(f"[SUPABASE] Failed to initialize client: {e}")
        return None


def is_supabase_enabled() -> bool:
    """Check if Supabase is available and configured."""
    return get_supabase() is not None