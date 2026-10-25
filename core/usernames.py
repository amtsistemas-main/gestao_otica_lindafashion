"""Username login on top of Supabase Auth (which requires an e-mail).

Each login uses the internal address <username>@usuarios.local: nobody types it and it never
receives e-mails. The same domain is used by the Edge Function admin-users.
"""
from __future__ import annotations

import re

USERNAME_DOMAIN = "usuarios.local"
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
USERNAME_RULES = "3 a 32 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado (começando por letra ou número)."


def normalize_username(raw: str | None) -> str:
    return (raw or "").strip().lower()


def is_valid_username(raw: str | None) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(normalize_username(raw)))


def login_to_email(login: str) -> str:
    """What the user typed in the login screen -> e-mail used by Supabase Auth.

    A username becomes the internal address; an e-mail (with "@") is kept for older logins.
    """
    value = (login or "").strip()
    if "@" in value:
        return value
    return f"{normalize_username(value)}@{USERNAME_DOMAIN}"


def username_from_email(email: str | None) -> str:
    """Display name of the login: the username for internal addresses, else the e-mail."""
    value = (email or "").strip()
    if value.lower().endswith("@" + USERNAME_DOMAIN):
        return value.split("@", 1)[0]
    return value
