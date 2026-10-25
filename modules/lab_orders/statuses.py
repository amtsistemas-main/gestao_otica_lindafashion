"""Single source of truth for the order / laboratory workflow."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrderStatus:
    code: str
    label: str
    color: str
    icon: str
    customer_facing: bool
    default_message: str = ""


FLOW: tuple[OrderStatus, ...] = (
    OrderStatus("aguardando_envio", "Aguardando envio", "#64748B", "fa5s.inbox", True,
                "Olá, {{cliente}}! Recebemos o seu pedido {{pedido}} ({{descricao}}). Previsão de entrega: {{previsao}}. Avisaremos por aqui a cada etapa. — {{loja}}"),
    OrderStatus("enviado_laboratorio", "Enviado ao laboratório", "#1749C2", "fa5s.shipping-fast", True,
                "Olá, {{cliente}}! Seu pedido {{pedido}} ({{descricao}}) foi enviado ao laboratório. Previsão: {{previsao}}. — {{loja}}"),
    OrderStatus("em_producao", "Em produção", "#7C3AED", "fa5s.cogs", True,
                "Olá, {{cliente}}! Seu pedido {{pedido}} ({{descricao}}) está em produção. Previsão: {{previsao}}. — {{loja}}"),
    OrderStatus("recebido", "Recebido", "#0E7490", "fa5s.box-open", False),
    OrderStatus("em_conferencia", "Em conferência", "#B7791F", "fa5s.search", False),
    OrderStatus("pronto_retirada", "Pronto para retirada", "#0E8A5B", "fa5s.glasses", True,
                "Olá, {{cliente}}! Boas notícias: seu pedido {{pedido}} ({{descricao}}) está pronto para retirada. — {{loja}}"),
    OrderStatus("entregue", "Entregue", "#102957", "fa5s.check-circle", True,
                "Olá, {{cliente}}! Registramos a entrega do pedido {{pedido}}. Obrigado por escolher a {{loja}}!"),
)
CANCELLED = OrderStatus("cancelado", "Cancelado", "#C03030", "fa5s.ban", True,
                        "Olá, {{cliente}}. O pedido {{pedido}} ({{descricao}}) foi cancelado. Fale conosco se precisar de ajuda. — {{loja}}")
ALL_STATUSES: tuple[OrderStatus, ...] = FLOW + (CANCELLED,)
BY_CODE = {status.code: status for status in ALL_STATUSES}
CLOSED = {"entregue", "cancelado"}
OCCURRENCE_TYPES = {
    "atraso": "Atraso",
    "erro_laboratorio": "Erro do laboratório",
    "retrabalho": "Retrabalho",
    "avaria": "Avaria / quebra",
    "garantia": "Garantia",
    "outro": "Outro",
}


def label(code: str) -> str:
    status = BY_CODE.get(code)
    return status.label if status else (code or "—")


def color(code: str) -> str:
    status = BY_CODE.get(code)
    return status.color if status else "#64748B"


def next_status(code: str) -> OrderStatus | None:
    """Next stage in the flow, or None for delivered/cancelled orders."""
    codes = [status.code for status in FLOW]
    if code not in codes or code == codes[-1]:
        return None
    return FLOW[codes.index(code) + 1]


def skips_quality_check(current: str, target: str) -> bool:
    """True when an order would be released to the customer without passing 'em_conferencia'."""
    codes = [status.code for status in FLOW]
    if target not in ("pronto_retirada", "entregue") or current not in codes:
        return False
    return codes.index(current) < codes.index("em_conferencia")


def template_statuses() -> list[OrderStatus]:
    return [status for status in ALL_STATUSES if status.customer_facing]
