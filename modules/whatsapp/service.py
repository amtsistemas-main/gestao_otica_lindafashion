"""Store WhatsApp: connection by QR Code and automatic sending through the message queue.

Connection and delivery run in Edge Functions (whatsapp-connect, whatsapp-send); messages are
queued by the validated database function enqueue_whatsapp_message, which takes the number
from the customer record. Without a connected WhatsApp the app keeps the manual flow (wa.me).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.edge_functions import EdgeFunctionError, invoke_edge_function
from core.organization import OrganizationContext
from core.phone import format_br_phone

DOCUMENTS_BUCKET = "whatsapp-documents"
STATUS_LABELS = {
    "connected": "Conectado",
    "connecting": "Aguardando a leitura do QR Code",
    "disconnected": "Desconectado",
}
_CACHE_SECONDS = 30
_cache: dict[str, tuple[float, "WhatsAppStatus"]] = {}


class WhatsAppError(RuntimeError):
    pass


@dataclass(slots=True)
class WhatsAppStatus:
    status: str = "disconnected"
    phone_number: str = ""
    profile_name: str = ""
    last_error: str = ""
    configured: bool = True

    @property
    def is_connected(self) -> bool:
        return self.status == "connected"

    @property
    def label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def phone_display(self) -> str:
        return format_br_phone(self.phone_number) if self.phone_number else ""

    @classmethod
    def from_mapping(cls, data: dict | None) -> "WhatsAppStatus":
        data = data or {}
        return cls(
            status=str(data.get("status") or "disconnected"),
            phone_number=str(data.get("phone_number") or ""),
            profile_name=str(data.get("profile_name") or ""),
            last_error=str(data.get("last_error") or ""),
            configured=bool(data.get("configured", True)),
        )


def describe_result(result: dict) -> tuple[bool, str]:
    """(sent?, message for the user) from a whatsapp-send response."""
    status = str(result.get("status") or "")
    error = str(result.get("error") or "")
    if status == "sent":
        return True, "Enviado pelo WhatsApp da loja ✓"
    if status in ("retry", "pending", "processing"):
        return False, "Não foi possível enviar agora; o sistema tentará de novo automaticamente." + (
            f"\nMotivo: {error}" if error else "")
    return False, error or "O envio não foi concluído."


class WhatsAppService:
    def __init__(self, ctx: OrganizationContext | None) -> None:
        self._ctx = ctx

    @property
    def available(self) -> bool:
        return self._ctx is not None

    def _invoke(self, name: str, payload: dict) -> dict:
        try:
            return invoke_edge_function(self._ctx, name, payload)
        except EdgeFunctionError as exc:
            raise WhatsAppError(str(exc)) from exc

    # ---- connection -------------------------------------------------------
    def cached_status(self) -> WhatsAppStatus:
        """Fast check (table kept up to date by the gateway webhook); cached for 30 s."""
        if self._ctx is None:
            return WhatsAppStatus()
        key = self._ctx.organization_id
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
            return cached[1]
        try:
            rows = (
                self._ctx.client.table("whatsapp_connections")
                .select("status,phone_number,profile_name,last_error")
                .eq("organization_id", key).limit(1).execute().data or []
            )
        except Exception:
            rows = []
        status = WhatsAppStatus.from_mapping(rows[0] if rows else None)
        _cache[key] = (time.monotonic(), status)
        return status

    def _remember(self, status: WhatsAppStatus) -> WhatsAppStatus:
        if self._ctx is not None:
            _cache[self._ctx.organization_id] = (time.monotonic(), status)
        return status

    def live_status(self) -> WhatsAppStatus:
        return self._remember(WhatsAppStatus.from_mapping(self._invoke("whatsapp-connect", {"action": "status"})))

    def connect(self) -> tuple[WhatsAppStatus, str, str]:
        """Starts the connection; returns (status, QR Code data URL, pairing code)."""
        data = self._invoke("whatsapp-connect", {"action": "connect"})
        status = self._remember(WhatsAppStatus.from_mapping(data))
        return status, str(data.get("qr_base64") or ""), str(data.get("pairing_code") or "")

    def disconnect(self) -> WhatsAppStatus:
        return self._remember(WhatsAppStatus.from_mapping(self._invoke("whatsapp-connect", {"action": "disconnect"})))

    def send_test(self, number: str) -> None:
        self._invoke("whatsapp-connect", {"action": "test", "number": number})

    # ---- sending ----------------------------------------------------------
    def _enqueue(self, customer_id: str | None, number: str, message: str, event_type: str,
                 attachment_path: str = "", attachment_name: str = "", dedupe_key: str | None = None) -> str:
        try:
            outbox_id = self._ctx.client.rpc("enqueue_whatsapp_message", {
                "p_organization_id": self._ctx.organization_id,
                "p_customer_id": customer_id,
                "p_recipient": number,
                "p_message": message,
                "p_event_type": event_type,
                "p_attachment_path": attachment_path,
                "p_attachment_name": attachment_name,
                "p_dedupe_key": dedupe_key,
            }).execute().data
        except Exception as exc:
            text = getattr(exc, "message", None) or str(exc)
            raise WhatsAppError(str(text)) from exc
        if isinstance(outbox_id, list):
            outbox_id = outbox_id[0] if outbox_id else None
        if not outbox_id:
            raise WhatsAppError("A mensagem não foi registrada para envio.")
        return str(outbox_id)

    def _flush(self, outbox_id: str) -> dict:
        try:
            return self._invoke("whatsapp-send", {"outbox_id": outbox_id})
        except WhatsAppError as exc:
            # Queued anyway: the scheduled worker will retry.
            return {"status": "retry", "error": str(exc)}

    def send_text(self, customer_id: str, message: str, event_type: str = "crm_message",
                  dedupe_key: str | None = None) -> dict:
        if self._ctx is None:
            raise WhatsAppError("Disponível somente com login no Supabase.")
        outbox_id = self._enqueue(customer_id, "", message, event_type, dedupe_key=dedupe_key)
        return self._flush(outbox_id)

    def send_document(self, customer_id: str | None, number: str, pdf_path: str | Path, file_name: str,
                      caption: str) -> dict:
        if self._ctx is None:
            raise WhatsAppError("Disponível somente com login no Supabase.")
        data = Path(pdf_path).read_bytes()
        storage_path = f"{self._ctx.organization_id}/{uuid4().hex}.pdf"
        try:
            self._ctx.client.storage.from_(DOCUMENTS_BUCKET).upload(
                storage_path, data, {"content-type": "application/pdf"})
        except Exception as exc:
            raise WhatsAppError(f"Não foi possível preparar o documento para envio: {exc}") from exc
        outbox_id = self._enqueue(customer_id, number, caption, "sales_document",
                                  attachment_path=storage_path, attachment_name=file_name)
        return self._flush(outbox_id)


class WhatsAppDocumentSender:
    """Automatic document sending used by the PDF viewer (ui stays independent of this module)."""

    def __init__(self, service: WhatsAppService, customer_id: str | None, customer_name: str = "",
                 customer_phone: str = "") -> None:
        self._service = service
        self._customer_id = customer_id
        self._customer_name = customer_name
        self._customer_phone = customer_phone

    def is_connected(self) -> bool:
        return self._service.available and self._service.cached_status().is_connected

    def needs_number(self) -> bool:
        """Walk-in sale without customer: the number is typed at sending time."""
        return self._customer_id is None

    def recipient_label(self) -> str:
        phone = format_br_phone(self._customer_phone)
        return " • ".join(part for part in (self._customer_name, phone) if part)

    def send(self, pdf_path: str | Path, file_name: str, caption: str, number: str = "") -> tuple[bool, str]:
        result = self._service.send_document(self._customer_id, number, pdf_path, file_name, caption)
        return describe_result(result)
