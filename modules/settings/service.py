"""Store-wide settings with safe defaults when the row (or migration) is missing."""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields

from core.organization import OrganizationContext

STORE_IDENTITY_FIELDS = (
    "store_name", "store_document", "store_phone", "store_whatsapp",
    "store_email", "store_address", "store_website", "document_terms",
)


@dataclass(slots=True)
class StoreSettings:
    max_discount_percent: float = 10.0
    prescription_validity_months: int = 12
    followup_days_after_delivery: int = 7
    review_reminder_days_before: int = 30
    # Identificação da loja impressa nos documentos (migration 202610250009).
    store_name: str = ""
    store_document: str = ""
    store_phone: str = ""
    store_whatsapp: str = ""
    store_email: str = ""
    store_address: str = ""
    store_website: str = ""
    quote_validity_days: int = 7
    document_terms: str = ""


def load_store_settings(ctx: OrganizationContext | None) -> StoreSettings:
    if ctx is None:
        return StoreSettings()
    try:
        rows = (
            ctx.client.table("organization_settings").select("*")
            .eq("organization_id", ctx.organization_id).limit(1).execute().data or []
        )
    except Exception:
        return StoreSettings()
    if not rows:
        return StoreSettings()
    row = rows[0]
    defaults = StoreSettings()
    return StoreSettings(
        max_discount_percent=float(row.get("max_discount_percent") if row.get("max_discount_percent") is not None else defaults.max_discount_percent),
        prescription_validity_months=int(row.get("prescription_validity_months") or defaults.prescription_validity_months),
        followup_days_after_delivery=int(row.get("followup_days_after_delivery") or defaults.followup_days_after_delivery),
        review_reminder_days_before=int(row.get("review_reminder_days_before") if row.get("review_reminder_days_before") is not None else defaults.review_reminder_days_before),
        quote_validity_days=int(row.get("quote_validity_days") or defaults.quote_validity_days),
        **{name: str(row.get(name) or "") for name in STORE_IDENTITY_FIELDS},
    )


def save_store_settings(ctx: OrganizationContext, settings: StoreSettings) -> None:
    record = {**asdict(settings), "organization_id": ctx.organization_id, "updated_by": ctx.user_id}
    try:
        ctx.client.table("organization_settings").upsert(record, on_conflict="organization_id").execute()
    except Exception as exc:
        # Banco sem a migration 202610250009: grava ao menos as regras comerciais.
        if "store_" not in str(exc) and "document_terms" not in str(exc) and "quote_validity" not in str(exc):
            raise
        legacy = {item.name for item in fields(StoreSettings)} - set(STORE_IDENTITY_FIELDS) - {"quote_validity_days"}
        ctx.client.table("organization_settings").upsert(
            {key: value for key, value in record.items() if key in legacy or key in ("organization_id", "updated_by")},
            on_conflict="organization_id",
        ).execute()
