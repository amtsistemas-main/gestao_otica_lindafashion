"""Environment-backed application settings."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _env_files() -> list[Path]:
    """Configuration sources, highest priority first.

    1. %APPDATA%\\OticaLindaFashion\\.env — per-machine override (support can change it);
    2. .env next to the program (installed app) or in the project folder (development);
    3. app.env embedded by the installer build (public URL and publishable key only).
    """
    frozen = getattr(sys, "frozen", False)
    base = Path(sys.executable).parent if frozen else Path(__file__).resolve().parents[1]
    files = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        files.append(Path(appdata) / "OticaLindaFashion" / ".env")
    files.append(base / ".env")
    if frozen:
        files.append(Path(getattr(sys, "_MEIPASS", base)) / "app.env")
    return files


for _env_file in _env_files():
    if _env_file.is_file():
        load_dotenv(_env_file, override=False)  # earlier files win

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
