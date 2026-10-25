"""Store-wide settings with safe defaults when the row (or migration) is missing."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from core.organization import OrganizationContext


@dataclass(slots=True)
class StoreSettings:
    max_discount_percent: float = 10.0
    prescription_validity_months: int = 12
    followup_days_after_delivery: int = 7
    review_reminder_days_before: int = 30


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
    )


def save_store_settings(ctx: OrganizationContext, settings: StoreSettings) -> None:
    record = {**asdict(settings), "organization_id": ctx.organization_id, "updated_by": ctx.user_id}
    ctx.client.table("organization_settings").upsert(record, on_conflict="organization_id").execute()
