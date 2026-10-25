"""Resolve the authenticated user's organization context once per window."""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


@dataclass(frozen=True, slots=True)
class OrganizationContext:
    client: object
    organization_id: str
    user_id: str
    role: str

    @property
    def is_manager(self) -> bool:
        """Owners and admins may exceed the store discount limit and edit settings."""
        return self.role in ("owner", "admin")


def current_organization(module_label: str = "Este módulo") -> OrganizationContext:
    if not session_manager.is_authenticated or not get_settings().supabase_configured:
        raise ConfigurationError(f"{module_label} exige login e configuração do Supabase.")
    client = get_supabase_client()
    session = session_manager.current
    rows = (
        client.table("organization_members")
        .select("organization_id,role")
        .eq("user_id", session.user_id)
        .eq("active", True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
    return OrganizationContext(
        client=client,
        organization_id=str(rows[0]["organization_id"]),
        user_id=session.user_id,
        role=str(rows[0].get("role") or "member"),
    )
