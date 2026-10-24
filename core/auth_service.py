"""Supabase email/password authentication service."""
from __future__ import annotations

import logging

from core.exceptions import AuthenticationError, ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class AuthService:
    def sign_in(self, email: str, password: str) -> None:
        normalized_email = email.strip()
        if not normalized_email or not password:
            raise AuthenticationError("Informe o e-mail e a senha.")

        try:
            response = get_supabase_client().auth.sign_in_with_password(
                {"email": normalized_email, "password": password}
            )
            user = response.user
            if user is None or not user.id:
                raise AuthenticationError("Não foi possível validar o acesso.")
            session_manager.start(user_id=user.id, email=user.email or normalized_email)
        except (AuthenticationError, ConfigurationError):
            raise
        except Exception as exc:
            # Provider errors can include internal details; keep the UI message generic.
            logger.info("Falha de autenticação Supabase.")
            raise AuthenticationError(
                "Não foi possível entrar. Confira os dados e tente novamente."
            ) from exc

    def sign_out(self) -> None:
        try:
            if session_manager.is_authenticated:
                get_supabase_client().auth.sign_out()
        except Exception:
            logger.warning("Falha ao encerrar a sessão remota.")
        finally:
            session_manager.clear()
