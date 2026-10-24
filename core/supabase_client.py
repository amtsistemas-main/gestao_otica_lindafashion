"""Lazy Supabase client factory.

Only public client credentials belong in a desktop application. Enforce access
control with database RLS policies; never ship a service-role key here.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from supabase import Client, create_client

from config.settings import get_settings
from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise ConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no arquivo .env."
        )
    try:
        return create_client(settings.supabase_url, settings.supabase_publishable_key)
    except Exception as exc:
        # Do not log credentials or the raw provider exception.
        logger.warning("Não foi possível inicializar o cliente Supabase.")
        raise ConfigurationError(
            "Não foi possível configurar a conexão com o serviço online."
        ) from exc
