"""Resolve the authenticated user's organization context once per window."""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from core.exceptions import ConfigurationError
from core.permissions import can_access, normalize_modules
from core.session_manager import session_manager
from core.supabase_client import get_supabase_client


@dataclass(frozen=True, slots=True)
class OrganizationContext:
    client: object
    organization_id: str
    user_id: str
    role: str
    # None = every module (owners/admins, or members without restriction).
    allowed_modules: frozenset[str] | None = None

    @property
    def is_manager(self) -> bool:
        """Owners and admins may exceed the store discount limit and edit settings."""
        return self.role in ("owner", "admin")

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    def can_access(self, nav_module: str | None) -> bool:
        return can_access(self.role, self.allowed_modules, nav_module)


def current_organization(module_label: str = "Este módulo") -> OrganizationContext:
    if not session_manager.is_authenticated or not get_settings().supabase_configured:
        raise ConfigurationError(f"{module_label} exige login e configuração do Supabase.")
    client = get_supabase_client()
    session = session_manager.current

    def membership(columns: str) -> list[dict]:
        return (
            client.table("organization_members").select(columns)
            .eq("user_id", session.user_id).eq("active", True).limit(1).execute().data or []
        )

    try:
        rows = membership("organization_id,role,allowed_modules")
    except Exception:
        # Banco ainda sem a migration 202610250010: sem restrição por módulo.
        rows = membership("organization_id,role")
    if not rows:
        raise ConfigurationError("Seu usuário não possui vínculo ativo com uma organização.")
    row = rows[0]
    return OrganizationContext(
        client=client,
        organization_id=str(row["organization_id"]),
        user_id=session.user_id,
        role=str(row.get("role") or "member"),
        allowed_modules=normalize_modules(row.get("allowed_modules")),
    )
