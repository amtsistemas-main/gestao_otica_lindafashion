"""In-memory authenticated session state."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserSession:
    user_id: str
    email: str


class SessionManager:
    """Small in-memory session holder; never persists access tokens to disk."""

    def __init__(self) -> None:
        self._session: UserSession | None = None

    @property
    def current(self) -> UserSession | None:
        return self._session

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None

    def start(self, user_id: str, email: str) -> None:
        self._session = UserSession(user_id=user_id, email=email)

    def clear(self) -> None:
        self._session = None


session_manager = SessionManager()
