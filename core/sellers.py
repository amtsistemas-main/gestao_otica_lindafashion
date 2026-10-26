"""Salespeople of the store: the active users created by the administrator."""
from __future__ import annotations

from typing import Any

from core.permissions import ROLE_LABELS
from core.usernames import username_from_email


def seller_name(member: dict[str, Any]) -> str:
    return str(member.get("display_name") or member.get("username")
               or username_from_email(str(member.get("email") or "")) or "Usuário")


def load_sellers(ctx: Any, include_inactive: bool = False) -> list[dict[str, Any]]:
    """[{user_id, name, role, active}] sorted by name; inactive users only for showing past sales."""
    if ctx is None:
        return [{"user_id": "demo-1", "name": "Vendedor demonstração", "role": "member", "active": True},
                {"user_id": "demo-2", "name": "Gerente demonstração", "role": "admin", "active": True}]
    query = ctx.client.table("organization_members").select("user_id,display_name,username,email,role,active").eq(
        "organization_id", ctx.organization_id)
    if not include_inactive:
        query = query.eq("active", True)
    rows = query.execute().data or []
    sellers = [{"user_id": str(row["user_id"]), "name": seller_name(row), "role": str(row.get("role") or "member"),
                "active": bool(row.get("active", True))} for row in rows]
    return sorted(sellers, key=lambda seller: seller["name"].casefold())


def seller_label(seller: dict[str, Any]) -> str:
    return f"{seller['name']} ({ROLE_LABELS.get(seller['role'], 'Vendedor')})"
