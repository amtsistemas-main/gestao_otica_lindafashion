from types import SimpleNamespace

import pytest

from core.phone import format_br_phone, normalize_br_whatsapp
from modules.whatsapp import service as wa
from modules.whatsapp.service import WhatsAppDocumentSender, WhatsAppService, describe_result


# Same cases checked against SQL public.normalize_br_whatsapp (app and database must agree).
@pytest.mark.parametrize("raw, expected", [
    ("(82) 99999-1234", "5582999991234"),
    ("5582999991234", "5582999991234"),
    ("082 3333-4444", "558233334444"),
    ("13974253461", "5513974253461"),
    ("+351 912 345 678", "351912345678"),
    ("123", ""),
    ("", ""),
    (None, ""),
])
def test_normalize_br_whatsapp_matches_database_rules(raw, expected) -> None:
    assert normalize_br_whatsapp(raw) == expected


def test_format_br_phone_for_display() -> None:
    assert format_br_phone("5582999991234") == "(82) 99999-1234"
    assert format_br_phone("558233334444") == "(82) 3333-4444"


def test_describe_result_messages() -> None:
    assert describe_result({"status": "sent"})[0] is True
    sent, message = describe_result({"status": "retry", "error": "O WhatsApp da loja não está conectado."})
    assert not sent and "tentará de novo" in message and "não está conectado" in message
    assert describe_result({"status": "failed", "error": "Este número não possui WhatsApp."}) == (
        False, "Este número não possui WhatsApp.")


class _Query:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, _name):
        return lambda *args, **kwargs: self

    def execute(self):
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, connection_status="connected"):
        self.uploads, self.rpcs, self.invokes = [], [], []
        self._status = connection_status
        self.auth = SimpleNamespace(get_session=lambda: SimpleNamespace(access_token="user-token"))
        self.storage = SimpleNamespace(from_=lambda bucket: SimpleNamespace(
            upload=lambda path, data, options: self.uploads.append((bucket, path, len(data), options))))
        self.functions = SimpleNamespace(invoke=self._invoke)

    def table(self, _name):
        return _Query([{"status": self._status, "phone_number": "5582999991234", "profile_name": "Loja", "last_error": ""}])

    def rpc(self, name, params):
        self.rpcs.append((name, params))
        return _Query("outbox-1")

    def _invoke(self, name, invoke_options):
        self.invokes.append((name, invoke_options))
        return {"status": "sent"}


def _ctx(client):
    return SimpleNamespace(client=client, organization_id="org-1", user_id="user-1", role="member")


def test_document_is_uploaded_to_org_folder_queued_and_sent(tmp_path) -> None:
    wa._cache.clear()
    pdf = tmp_path / "os.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    client = FakeClient()
    sender = WhatsAppDocumentSender(WhatsAppService(_ctx(client)), "cust-1", "Mariana", "(82) 99999-1234")

    assert sender.is_connected() and not sender.needs_number()
    assert sender.send(pdf, "OS V-1.pdf", "Segue a sua OS") == (True, "Enviado pelo WhatsApp da loja ✓")

    bucket, path, size, options = client.uploads[0]
    assert bucket == "whatsapp-documents" and path.startswith("org-1/") and path.endswith(".pdf") and size > 0
    name, params = client.rpcs[0]
    assert name == "enqueue_whatsapp_message"
    assert params["p_customer_id"] == "cust-1" and params["p_event_type"] == "sales_document"
    assert params["p_attachment_path"] == path and params["p_attachment_name"] == "OS V-1.pdf"
    function, options = client.invokes[0]
    assert function == "whatsapp-send"
    assert options["body"] == {"outbox_id": "outbox-1", "organization_id": "org-1"}
    assert options["headers"]["Authorization"] == "Bearer user-token"


def test_walk_in_sale_needs_number_and_disconnected_store_is_detected() -> None:
    wa._cache.clear()
    sender = WhatsAppDocumentSender(WhatsAppService(_ctx(FakeClient("disconnected"))), None)
    assert sender.needs_number()
    assert not sender.is_connected()
    assert not WhatsAppDocumentSender(WhatsAppService(None), "c").is_connected()
