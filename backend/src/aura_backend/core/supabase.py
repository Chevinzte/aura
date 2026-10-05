from functools import lru_cache

from supabase import Client, create_client

from aura_backend.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Create the backend-only Supabase client using the project secret key."""
    settings = get_settings()
    return create_client(str(settings.supabase_url), settings.supabase_secret_key)
