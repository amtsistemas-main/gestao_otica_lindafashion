"""Prescription persistence: Supabase (tenant-scoped) and in-memory preview."""
from __future__ import annotations

from uuid import uuid4

from core.organization import OrganizationContext
from modules.prescriptions.models import Prescription


# Preview mode keeps prescriptions for the whole session (discarded when the app closes).
_PREVIEW_STORE: dict[str, Prescription] = {}


class PrescriptionRepository:
    def __init__(self, ctx: OrganizationContext | None) -> None:
        self._ctx = ctx
        self._memory = _PREVIEW_STORE

    @property
    def is_preview(self) -> bool:
        return self._ctx is None

    def list_for_customer(self, customer_id: str) -> list[Prescription]:
        if self._ctx is None:
            items = [item for item in self._memory.values() if item.customer_id == customer_id]
        else:
            rows = (
                self._ctx.client.table("customer_prescriptions").select("*")
                .eq("organization_id", self._ctx.organization_id)
                .eq("customer_id", customer_id)
                .order("prescribed_at", desc=True)
                .execute().data or []
            )
            items = [Prescription.from_mapping(row) for row in rows]
        return sorted(items, key=lambda item: (item.prescribed_at, item.created_at), reverse=True)

    def latest_for_customer(self, customer_id: str) -> Prescription | None:
        active = [item for item in self.list_for_customer(customer_id) if item.active]
        return active[0] if active else None

    def get(self, prescription_id: str) -> Prescription | None:
        if self._ctx is None:
            return self._memory.get(prescription_id)
        rows = (
            self._ctx.client.table("customer_prescriptions").select("*")
            .eq("organization_id", self._ctx.organization_id).eq("id", prescription_id)
            .limit(1).execute().data or []
        )
        return Prescription.from_mapping(rows[0]) if rows else None

    def save(self, prescription: Prescription) -> Prescription:
        prescription.normalize()
        problems = prescription.errors()
        if problems:
            raise ValueError("\n".join(problems))
        if self._ctx is None:
            if not prescription.id:
                prescription.id = str(uuid4())
            self._memory[prescription.id] = prescription
            return prescription
        record = prescription.to_record()
        record["organization_id"] = self._ctx.organization_id
        table = self._ctx.client.table("customer_prescriptions")
        if prescription.id:
            rows = (
                table.update(record).eq("id", prescription.id)
                .eq("organization_id", self._ctx.organization_id).execute().data or []
            )
        else:
            record["created_by"] = self._ctx.user_id
            rows = table.insert(record).execute().data or []
        if not rows:
            raise RuntimeError("A receita não foi confirmada pelo banco. Verifique as permissões da organização.")
        return Prescription.from_mapping(rows[0])
