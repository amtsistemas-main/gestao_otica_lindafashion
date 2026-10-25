"""Structured ophthalmic prescription with the same rules enforced by the database."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from typing import Any

EYES = ("od", "oe")
EYE_LABELS = {"od": "OD (olho direito)", "oe": "OE (olho esquerdo)"}
SOURCES = {"receita_externa": "Receita externa", "exame_interno": "Exame interno", "lensometria": "Lensometria (óculos atual)"}
EYE_FIELDS = ("sphere", "cylinder", "axis", "addition", "dnp", "near_dnp", "height", "prism", "prism_base")


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(Decimal(str(value).replace(",", ".")))
    except Exception:
        return None


def _is_quarter(value: float) -> bool:
    return abs(round(value * 4) - value * 4) < 1e-6


def format_diopter(value: float | None, plano: bool = False) -> str:
    """'+1,25' / '-0,75' / 'Plano' (sphere zero) / '—' when empty."""
    if value is None:
        return "—"
    if plano and abs(value) < 1e-9:
        return "Plano"
    return f"{value:+.2f}".replace(".", ",")


def format_number(value: float | None, decimals: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",") + suffix


@dataclass(slots=True)
class Prescription:
    id: str | None = None
    customer_id: str | None = None
    prescribed_at: date = field(default_factory=date.today)
    expires_at: date | None = None
    source: str = "receita_externa"
    prescriber_name: str = ""
    prescriber_registry: str = ""
    od_sphere: float | None = None
    od_cylinder: float | None = None
    od_axis: int | None = None
    od_addition: float | None = None
    od_dnp: float | None = None
    od_near_dnp: float | None = None
    od_height: float | None = None
    od_prism: float | None = None
    od_prism_base: str = ""
    oe_sphere: float | None = None
    oe_cylinder: float | None = None
    oe_axis: int | None = None
    oe_addition: float | None = None
    oe_dnp: float | None = None
    oe_near_dnp: float | None = None
    oe_height: float | None = None
    oe_prism: float | None = None
    oe_prism_base: str = ""
    lens_recommendation: str = ""
    notes: str = ""
    active: bool = True
    created_at: str = ""

    def eye(self, eye: str, name: str) -> Any:
        return getattr(self, f"{eye}_{name}")

    def normalize(self) -> None:
        """Round diopters to 0.25 D steps and drop an axis that has no cylinder."""
        for eye in EYES:
            for name in ("sphere", "cylinder", "addition"):
                value = self.eye(eye, name)
                if value is not None:
                    setattr(self, f"{eye}_{name}", round(value * 4) / 4)
            cylinder = self.eye(eye, "cylinder")
            if cylinder is not None and abs(cylinder) < 1e-9:
                setattr(self, f"{eye}_cylinder", None)
            if self.eye(eye, "cylinder") is None:
                setattr(self, f"{eye}_axis", None)

    def errors(self) -> list[str]:
        """Blocking problems; mirrors the database check constraints."""
        problems: list[str] = []
        if self.expires_at and self.expires_at < self.prescribed_at:
            problems.append("A validade não pode ser anterior à data da receita.")
        if self.source not in SOURCES:
            problems.append("Selecione a origem da receita.")
        has_power = False
        for eye in EYES:
            label = eye.upper()
            sphere, cylinder, axis = self.eye(eye, "sphere"), self.eye(eye, "cylinder"), self.eye(eye, "axis")
            addition = self.eye(eye, "addition")
            if sphere is not None or cylinder is not None:
                has_power = True
            if sphere is not None and (not -30 <= sphere <= 30 or not _is_quarter(sphere)):
                problems.append(f"{label}: esférico deve estar entre -30,00 e +30,00 em passos de 0,25.")
            if cylinder is not None and (not -15 <= cylinder <= 15 or not _is_quarter(cylinder)):
                problems.append(f"{label}: cilíndrico deve estar entre -15,00 e +15,00 em passos de 0,25.")
            if cylinder not in (None, 0) and axis is None:
                problems.append(f"{label}: informe o eixo — é obrigatório quando há cilíndrico.")
            if axis is not None and not 0 <= axis <= 180:
                problems.append(f"{label}: eixo deve estar entre 0 e 180°.")
            if addition is not None and (not 0.25 <= addition <= 4.5 or not _is_quarter(addition)):
                problems.append(f"{label}: adição deve estar entre +0,25 e +4,50 em passos de 0,25.")
            for name, low, high, title in (
                ("dnp", 20, 45, "DNP de longe"), ("near_dnp", 18, 45, "DNP de perto"),
                ("height", 8, 45, "altura de montagem"), ("prism", 0, 15, "prisma"),
            ):
                value = self.eye(eye, name)
                if value is not None and not low <= value <= high:
                    problems.append(f"{label}: {title} deve estar entre {low} e {high}.")
        if not has_power:
            problems.append("Informe ao menos o esférico ou o cilíndrico de um dos olhos.")
        return problems

    def warnings(self, validity_months: int = 12, today: date | None = None) -> list[str]:
        """Non-blocking clinical sanity checks that catch common typing mistakes."""
        today = today or date.today()
        notes: list[str] = []
        od_sph, oe_sph = self.od_sphere, self.oe_sphere
        if od_sph is not None and oe_sph is not None and abs(od_sph - oe_sph) >= 3:
            notes.append(f"Diferença de {format_number(abs(od_sph - oe_sph), 2)} D no esférico entre os olhos — confira a digitação.")
        od_cyl, oe_cyl = self.od_cylinder, self.oe_cylinder
        if od_cyl and oe_cyl and (od_cyl > 0) != (oe_cyl > 0):
            notes.append("Cilíndricos com sinais diferentes entre os olhos — confira a convenção (+/−) da receita.")
        if self.od_addition and self.oe_addition and abs(self.od_addition - self.oe_addition) > 0.5:
            notes.append("Adição muito diferente entre os olhos — normalmente é igual ou próxima.")
        for eye in EYES:
            far, near = self.eye(eye, "dnp"), self.eye(eye, "near_dnp")
            if far is not None and near is not None and near > far:
                notes.append(f"{eye.upper()}: DNP de perto maior que a de longe — normalmente é menor.")
        if self.od_dnp is not None and self.oe_dnp is not None and not 50 <= self.od_dnp + self.oe_dnp <= 76:
            notes.append(f"DNP total de {format_number(self.od_dnp + self.oe_dnp, 1)} mm fora da faixa usual (50–76 mm).")
        expiry = self.effective_expiry(validity_months)
        if expiry < today:
            notes.append(f"Receita vencida em {expiry.strftime('%d/%m/%Y')} — recomende novo exame.")
        return notes

    def effective_expiry(self, validity_months: int = 12) -> date:
        if self.expires_at:
            return self.expires_at
        month = self.prescribed_at.month - 1 + validity_months
        year = self.prescribed_at.year + month // 12
        month = month % 12 + 1
        day = min(self.prescribed_at.day, 28)
        return date(year, month, day)

    @property
    def is_progressive(self) -> bool:
        return bool(self.od_addition or self.oe_addition)

    def eye_summary(self, eye: str) -> str:
        """'-1,25 -0,50 × 180 Ad +2,00' style summary used in lists and documents."""
        sphere, cylinder, axis = self.eye(eye, "sphere"), self.eye(eye, "cylinder"), self.eye(eye, "axis")
        text = format_diopter(sphere, plano=True)
        if cylinder:
            text += f" {format_diopter(cylinder)} × {axis if axis is not None else '?'}°"
        addition = self.eye(eye, "addition")
        if addition:
            text += f"  Ad {format_diopter(addition)}"
        return text

    def near_sphere(self, eye: str) -> float | None:
        sphere, addition = self.eye(eye, "sphere"), self.eye(eye, "addition")
        if addition is None:
            return None
        return (sphere or 0.0) + addition

    def to_service_order_payload(self, frame: dict | None = None) -> dict:
        """Legacy structure read by the service-order PDF (longe / perto / armação)."""
        def text(value: float | int | None, diopter: bool = False) -> str:
            if value is None:
                return ""
            return format_diopter(float(value)) if diopter else format_number(float(value), 1 if isinstance(value, float) else 0)

        payload: dict[str, Any] = {"longe": {}, "perto": {}, "armacao": dict(frame or {})}
        for eye in EYES:
            payload["longe"][eye] = {
                "esf": text(self.eye(eye, "sphere"), True), "cil": text(self.eye(eye, "cylinder"), True),
                "eixo": str(self.eye(eye, "axis") if self.eye(eye, "axis") is not None else ""),
                "dnp": text(self.eye(eye, "dnp")),
            }
            payload["perto"][eye] = {
                "esf": text(self.near_sphere(eye), True), "cil": text(self.eye(eye, "cylinder"), True) if self.eye(eye, "addition") else "",
                "eixo": str(self.eye(eye, "axis") if self.eye(eye, "addition") and self.eye(eye, "axis") is not None else ""),
                "dnp": text(self.eye(eye, "near_dnp")), "alt": text(self.eye(eye, "height")),
                "ad": text(self.eye(eye, "addition"), True),
            }
        return payload

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Prescription:
        def parse_date(value: Any) -> date | None:
            if not value:
                return None
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                return None

        item = cls(
            id=str(data["id"]) if data.get("id") else None,
            customer_id=str(data["customer_id"]) if data.get("customer_id") else None,
            prescribed_at=parse_date(data.get("prescribed_at")) or date.today(),
            expires_at=parse_date(data.get("expires_at")),
            source=str(data.get("source") or "receita_externa"),
            prescriber_name=str(data.get("prescriber_name") or ""),
            prescriber_registry=str(data.get("prescriber_registry") or ""),
            lens_recommendation=str(data.get("lens_recommendation") or ""),
            notes=str(data.get("notes") or ""),
            active=bool(data.get("active", True)),
            created_at=str(data.get("created_at") or ""),
        )
        for eye in EYES:
            for name in EYE_FIELDS:
                key = f"{eye}_{name}"
                if name == "prism_base":
                    setattr(item, key, str(data.get(key) or ""))
                elif name == "axis":
                    value = _num(data.get(key))
                    setattr(item, key, int(value) if value is not None else None)
                else:
                    setattr(item, key, _num(data.get(key)))
        return item

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {}
        for item in fields(self):
            if item.name in ("id", "created_at"):
                continue
            value = getattr(self, item.name)
            if isinstance(value, date):
                value = value.isoformat()
            record[item.name] = value
        return record
