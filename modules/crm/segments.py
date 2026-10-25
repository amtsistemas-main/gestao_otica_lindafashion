"""Customer segmentation for repurchase campaigns (recency, frequency, value and prescription expiry)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SEGMENTS = {
    "receita_vencendo": ("Receita vencendo ou vencida", "Convite para novo exame — principal gatilho de recompra.", "fa5s.eye", "#B7791F"),
    "em_risco": ("Em risco", "Última compra entre 9 e 18 meses: momento ideal para reativar.", "fa5s.exclamation-triangle", "#C03030"),
    "fieis": ("Fiéis / alto valor", "3+ compras ou entre os 20% que mais gastam.", "fa5s.crown", "#7C3AED"),
    "novos": ("Novos clientes", "Primeira compra nos últimos 90 dias: cuide do pós-venda.", "fa5s.user-plus", "#0E8A5B"),
    "inativos": ("Inativos", "Sem compras há mais de 18 meses.", "fa5s.user-clock", "#64748B"),
    "sem_compra": ("Sem compra registrada", "Cadastrados que ainda não compraram.", "fa5s.user", "#64748B"),
    "aniversariantes": ("Aniversariantes do mês", "Oportunidade de relacionamento com benefício especial.", "fa5s.birthday-cake", "#2165F5"),
}
TASK_TYPES = {
    "pos_venda": "Pós-venda",
    "revisao_receita": "Revisão da receita",
    "aniversario": "Aniversário",
    "reativacao": "Reativação",
    "campanha": "Campanha",
    "outro": "Outro",
}


def _day(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    return date(start.year + month // 12, month % 12 + 1, min(start.day, 28))


@dataclass(slots=True)
class CustomerInsight:
    customer: dict
    purchases: int = 0
    total_spent: float = 0.0
    first_purchase: date | None = None
    last_purchase: date | None = None
    prescription_expiry: date | None = None
    segments: list[str] = field(default_factory=list)

    @property
    def days_since_purchase(self) -> int | None:
        return None if self.last_purchase is None else (date.today() - self.last_purchase).days

    @property
    def can_whatsapp(self) -> bool:
        digits = "".join(ch for ch in str(self.customer.get("whatsapp") or "") if ch.isdigit())
        return bool(self.customer.get("whatsapp_consent")) and len(digits) >= 10


def segment_customers(
    customers: list[dict], orders: list[dict], prescriptions: list[dict], *,
    today: date | None = None, validity_months: int = 12, review_days: int = 30,
) -> dict[str, CustomerInsight]:
    today = today or date.today()
    insights = {str(c["id"]): CustomerInsight(c) for c in customers if c.get("active", True)}

    for order in orders:
        if order.get("status") != "completed":
            continue
        insight = insights.get(str(order.get("customer_id")))
        when = _day(order.get("created_at"))
        if insight is None or when is None:
            continue
        insight.purchases += 1
        insight.total_spent += float(order.get("total") or 0)
        insight.first_purchase = min(filter(None, [insight.first_purchase, when]))
        insight.last_purchase = max(filter(None, [insight.last_purchase, when]))

    latest: dict[str, dict] = {}
    for item in prescriptions:
        if not item.get("active", True):
            continue
        key = str(item.get("customer_id"))
        prescribed = _day(item.get("prescribed_at"))
        current = latest.get(key)
        if prescribed and (current is None or prescribed > _day(current.get("prescribed_at"))):
            latest[key] = item
    for key, item in latest.items():
        if key in insights:
            insights[key].prescription_expiry = _day(item.get("expires_at")) or _add_months(_day(item.get("prescribed_at")), validity_months)

    spenders = sorted((i.total_spent for i in insights.values() if i.purchases), reverse=True)
    top_threshold = spenders[max(0, int(len(spenders) * 0.2) - 1)] if len(spenders) >= 5 else float("inf")

    for insight in insights.values():
        tags = insight.segments
        if insight.purchases == 0:
            tags.append("sem_compra")
        else:
            days = (today - insight.last_purchase).days
            if insight.purchases == 1 and (today - insight.first_purchase).days <= 90:
                tags.append("novos")
            if insight.purchases >= 3 or insight.total_spent >= top_threshold:
                tags.append("fieis")
            if 270 <= days <= 540:
                tags.append("em_risco")
            elif days > 540:
                tags.append("inativos")
        expiry = insight.prescription_expiry
        if expiry and (expiry - today).days <= review_days and (today - expiry).days <= 365:
            tags.append("receita_vencendo")
        birth = _day(insight.customer.get("birth_date"))
        if birth and birth.month == today.month and birth.year > 1900:
            tags.append("aniversariantes")
    return insights


def whatsapp_message(task_type: str, customer_name: str, store: str = "Ótica Linda Fashion") -> str:
    first = (customer_name or "").split(" ")[0] or "tudo bem"
    messages = {
        "pos_venda": f"Olá, {first}! Aqui é da {store}. Como está a adaptação aos seus óculos novos? Se precisar de qualquer ajuste, é só passar aqui — é cortesia!",
        "revisao_receita": f"Olá, {first}! Sua receita de óculos está perto de vencer. Que tal agendar um novo exame e conhecer as novidades em armações e lentes da {store}?",
        "aniversario": f"Feliz aniversário, {first}! A {store} preparou uma condição especial para você este mês. Venha nos visitar!",
        "reativacao": f"Olá, {first}! Sentimos sua falta na {store}. Chegaram novas coleções de armações e lentes — venha conferir!",
        "campanha": f"Olá, {first}! A {store} tem novidades e condições especiais para você. Posso te contar mais?",
    }
    return messages.get(task_type, f"Olá, {first}! Aqui é da {store}.")
