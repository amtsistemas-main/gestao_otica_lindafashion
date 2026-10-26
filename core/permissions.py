"""Module catalog used by the multi-user access control.

The keys match ``organization_members.allowed_modules`` and the Edge Function
``admin-users``. ``None`` as the allowed set means every module.
"""
from __future__ import annotations

from typing import Iterable

# (key, label, navigation module name)
MODULES: tuple[tuple[str, str, str], ...] = (
    ("vendas", "Vendas / PDV e pedidos", "Vendas"),
    ("clientes", "Clientes e receitas", "Clientes"),
    ("relacionamento", "Relacionamento (CRM)", "Relacionamento"),
    ("produtos", "Produtos", "Produtos"),
    ("estoque", "Estoque e compras", "Estoque"),
    ("fornecedores", "Fornecedores", "Fornecedores"),
    ("financeiro", "Financeiro", "Financeiro"),
    ("indicadores", "Indicadores", "Indicadores"),
    ("analises", "Análises", "Análises"),
    ("configuracoes", "Configurações (nome de exibição)", "Configurações"),
)
MODULE_KEYS = tuple(key for key, _label, _nav in MODULES)
MODULE_LABELS = {key: label for key, label, _nav in MODULES}
NAV_TO_KEY = {nav: key for key, _label, nav in MODULES}
NAV_TO_KEY["Pedidos"] = "vendas"
ROLE_LABELS = {"owner": "Dono", "admin": "Administrador", "member": "Vendedor"}
# Suggested access for a new salesperson.
DEFAULT_MEMBER_MODULES = ("vendas", "clientes", "relacionamento", "produtos")


def normalize_modules(values: Iterable[str] | None) -> frozenset[str] | None:
    if values is None:
        return None
    return frozenset(value for value in values if value in MODULE_KEYS)


def can_access(role: str, allowed: frozenset[str] | None, nav_module: str | None) -> bool:
    """Overview is always visible; owners/admins see everything."""
    if nav_module is None:
        return True
    if role in ("owner", "admin") or allowed is None:
        return True
    key = NAV_TO_KEY.get(nav_module)
    return key is None or key in allowed


def modules_summary(role: str, allowed: Iterable[str] | None) -> str:
    if role in ("owner", "admin") or allowed is None:
        return "Todos os módulos"
    keys = [key for key in MODULE_KEYS if key in set(allowed)]
    if not keys:
        return "Somente visão geral"
    return ", ".join(MODULE_LABELS[key].split(" (")[0].split(" e ")[0] for key in keys)
