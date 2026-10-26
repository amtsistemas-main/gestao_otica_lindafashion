"""Brazilian WhatsApp numbers: one normalization for the whole app (mirrors SQL normalize_br_whatsapp)."""
from __future__ import annotations

import re


def normalize_br_whatsapp(raw: str | None) -> str:
    """Digits in international format (55 + DDD + number) or '' when invalid.

    '(82) 99999-1234' -> '5582999991234'; '082 3333-4444' -> '558233334444'.
    """
    digits = re.sub(r"\D", "", raw or "").lstrip("0")
    if len(digits) in (10, 11):
        return "55" + digits
    if len(digits) in (12, 13) and digits.startswith("55"):
        return digits
    if 12 <= len(digits) <= 15:
        return digits
    return ""


def is_valid_whatsapp(raw: str | None) -> bool:
    return bool(normalize_br_whatsapp(raw))


def format_br_phone(raw: str | None) -> str:
    """'5582999991234' -> '(82) 99999-1234' for display; other formats are returned as typed."""
    digits = normalize_br_whatsapp(raw)
    if digits.startswith("55") and len(digits) in (12, 13):
        local = digits[2:]
        ddd, number = local[:2], local[2:]
        return f"({ddd}) {number[:-4]}-{number[-4:]}"
    return raw or ""
