"""Environment-backed application settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# This URL is public project metadata, not a credential. The publishable key
# must still be supplied locally and is never committed to the repository.
DEFAULT_SUPABASE_URL = "https://swlccwcykxmvwptzxrxt.supabase.co"


@dataclass(frozen=True, slots=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    log_level: str

    @property
    def supabase_configured(self) -> bool:
        return (
            bool(self.supabase_url)
            and bool(self.supabase_publishable_key)
            and "YOUR_PROJECT" not in self.supabase_url
            and "YOUR_PUBLIC_" not in self.supabase_publishable_key
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip(),
        supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
    )
