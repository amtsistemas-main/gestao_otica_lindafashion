"""Order/laboratory persistence: Supabase (tenant-scoped) or in-memory preview data."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from core.organization import OrganizationContext

_STAGE_STAMPS = {
    "enviado_laboratorio": "sent_at",
    "recebido": "received_at",
    "em_conferencia": "checked_at",
    "pronto_retirada": "completed_at",
    "entregue": "delivered_at",
}


def _preview_orders() -> list[dict]:
    today = date.today()

    def order(number, customer_id, description, status, lab_days, client_days, lab_cost):
        return {
            "id": str(uuid4()), "customer_id": customer_id, "order_number": number, "description": description,
            "lens_description": description, "status": status, "laboratory_id": "lab-demo",
            "lab_order_number": f"LAB-{number[-3:]}", "lab_cost": lab_cost,
            "lab_expected_at": (today + timedelta(days=lab_days)).isoformat(),
            "expected_at": (today + timedelta(days=client_days)).isoformat(),
            "created_at": (datetime.now() - timedelta(days=6)).isoformat(), "notes": "",
            "frame_measurements": {}, "prescription_id": None, "sales_order_id": None,
        }

    return [
        order("V-20261020-001", "demo-1", "Multifocal 1.67 antirreflexo + armação acetato", "em_producao", 2, 5, 380.0),
        order("V-20261021-002", "demo-2", "Monofocal 1.56 filtro azul", "aguardando_envio", 4, 7, 120.0),
        order("V-20261018-003", "demo-1", "Lentes de contato mensais", "em_conferencia", -1, 1, 90.0),
        order("V-20261015-004", "demo-2", "Monofocal 1.60 fotossensível", "pronto_retirada", -3, -1, 210.0),
        order("V-20261012-005", "demo-1", "Óculos solar com grau", "enviado_laboratorio", -2, 0, 260.0),
    ]


class LabOrderRepository:
    def __init__(self, ctx: OrganizationContext | None) -> None:
        self._ctx = ctx
        self._orders = _preview_orders() if ctx is None else []
        self._events: dict[str, list[dict]] = {}
        self._occurrences: dict[str, list[dict]] = {}

    @property
    def is_preview(self) -> bool:
        return self._ctx is None

    # Reference data -------------------------------------------------------
    def customers(self) -> list[dict]:
        if self._ctx is None:
            return [
                {"id": "demo-1", "full_name": "Mariana Costa", "whatsapp": "(82) 99999-1234"},
                {"id": "demo-2", "full_name": "João Santos", "whatsapp": "(82) 98888-4321"},
            ]
        return list(
            self._ctx.client.table("customers").select("id,full_name,whatsapp,active")
            .eq("organization_id", self._ctx.organization_id).order("full_name").execute().data or []
        )

    def laboratories(self) -> list[dict]:
        if self._ctx is None:
            return [{"id": "lab-demo", "name": "Laboratório Óptico Demo", "trade_name": "Lab Demo"}]
        return list(
            self._ctx.client.table("suppliers").select("id,name,trade_name,active")
            .eq("organization_id", self._ctx.organization_id).eq("active", True).order("name").execute().data or []
        )

    # Orders ---------------------------------------------------------------
    def list_orders(self, customer_id: str | None = None) -> list[dict]:
        if self._ctx is None:
            rows = [dict(row) for row in self._orders]
            return [row for row in rows if not customer_id or row["customer_id"] == customer_id]
        query = (
            self._ctx.client.table("customer_orders").select("*")
            .eq("organization_id", self._ctx.organization_id)
        )
        if customer_id:
            query = query.eq("customer_id", customer_id)
        return list(query.order("created_at", desc=True).limit(1000).execute().data or [])

    def save(self, record: dict, order_id: str | None = None) -> dict:
        if self._ctx is None:
            if order_id:
                for row in self._orders:
                    if row["id"] == order_id:
                        row.update(record)
                        return dict(row)
            new_row = {"id": str(uuid4()), "status": "aguardando_envio", "created_at": datetime.now().isoformat(), **record}
            self._orders.insert(0, new_row)
            return dict(new_row)
        table = self._ctx.client.table("customer_orders")
        if order_id:
            rows = table.update(record).eq("id", order_id).eq("organization_id", self._ctx.organization_id).execute().data or []
        else:
            rows = table.insert({**record, "organization_id": self._ctx.organization_id, "created_by": self._ctx.user_id}).execute().data or []
        if not rows:
            raise RuntimeError("O pedido não foi confirmado pelo banco. Verifique as permissões da organização.")
        return rows[0]

    def set_status(self, order: dict, new_status: str) -> None:
        if self._ctx is None:
            for row in self._orders:
                if row["id"] == order["id"]:
                    previous = row.get("status", "")
                    row["status"] = new_status
                    stamp = _STAGE_STAMPS.get(new_status)
                    if stamp and not row.get(stamp):
                        row[stamp] = datetime.now().isoformat()
                    self._events.setdefault(order["id"], []).insert(0, {
                        "previous_status": previous, "new_status": new_status,
                        "changed_at": datetime.now().isoformat(), "note": "",
                    })
            return
        # Stage timestamps and the history event are written by database triggers.
        self.save({"status": new_status}, order["id"])

    def events(self, order_id: str) -> list[dict]:
        if self._ctx is None:
            return list(self._events.get(order_id, []))
        return list(
            self._ctx.client.table("customer_order_events").select("previous_status,new_status,changed_at,note")
            .eq("organization_id", self._ctx.organization_id).eq("order_id", order_id)
            .order("changed_at", desc=True).limit(200).execute().data or []
        )

    def occurrences(self, order_id: str) -> list[dict]:
        if self._ctx is None:
            return list(self._occurrences.get(order_id, []))
        return list(
            self._ctx.client.table("customer_order_occurrences").select("*")
            .eq("organization_id", self._ctx.organization_id).eq("order_id", order_id)
            .order("created_at", desc=True).execute().data or []
        )

    def add_occurrence(self, order_id: str, occurrence_type: str, description: str, cost: float) -> None:
        record = {"order_id": order_id, "occurrence_type": occurrence_type, "description": description, "cost": round(cost, 2)}
        if self._ctx is None:
            self._occurrences.setdefault(order_id, []).insert(0, {
                **record, "id": str(uuid4()), "created_at": datetime.now().isoformat(), "resolved_at": None,
            })
            return
        self._ctx.client.table("customer_order_occurrences").insert({
            **record, "organization_id": self._ctx.organization_id, "created_by": self._ctx.user_id,
        }).execute()

    def resolve_occurrence(self, order_id: str, occurrence_id: str) -> None:
        now = datetime.now().astimezone().isoformat()
        if self._ctx is None:
            for item in self._occurrences.get(order_id, []):
                if item["id"] == occurrence_id:
                    item["resolved_at"] = now
            return
        self._ctx.client.table("customer_order_occurrences").update({"resolved_at": now}).eq(
            "id", occurrence_id).eq("organization_id", self._ctx.organization_id).execute()
