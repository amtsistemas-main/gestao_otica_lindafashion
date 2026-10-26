"""Connecting the store WhatsApp by QR Code, and the WhatsApp card shown in Settings."""
from __future__ import annotations

import base64

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QVBoxLayout, QWidget,
)

from modules.whatsapp.service import WhatsAppService, WhatsAppStatus
from ui.components.background import run_in_background
from ui.components.ui_kit import make_button

POLL_MS = 3000          # connection status check while the QR Code is shown
QR_REFRESH_MS = 40000   # WhatsApp QR Codes expire in about a minute
MAX_QR_REFRESHES = 5    # then the user generates a new one (avoids gateway limits)
QR_SIZE = 260

RISK_TEXT = (
    "A conexão por QR Code usa o WhatsApp da loja como o WhatsApp Web. Use-a apenas para mensagens "
    "de atendimento (pedidos, documentos, pós-venda) a clientes que autorizaram o contato. Envios em massa "
    "ou mensagens não solicitadas podem levar ao bloqueio do número pelo WhatsApp."
)


def _title_bar(title: str, subtitle: str) -> QFrame:
    bar = QFrame()
    bar.setObjectName("windowTitleBar")
    layout = QVBoxLayout(bar)
    layout.setContentsMargins(18, 13, 18, 13)
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setObjectName("windowTitle")
    caption = QLabel(subtitle)
    caption.setObjectName("windowSubtitle")
    caption.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(caption)
    return bar


def qr_pixmap(data_url: str, size: int = 300) -> QPixmap:
    pixmap = QPixmap()
    payload = data_url.split(",", 1)[-1] if data_url else ""
    if payload:
        try:
            pixmap.loadFromData(base64.b64decode(payload))
        except (ValueError, TypeError):
            return QPixmap()
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class ConnectWhatsAppDialog(QDialog):
    def __init__(self, service: WhatsAppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._busy = False
        self._refreshes = 0
        self.connected_status: WhatsAppStatus | None = None
        self.setWindowTitle("Conectar WhatsApp — Ótica Linda Fashion")
        self.resize(700, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(_title_bar("Conectar WhatsApp da loja",
                                  "Escaneie o QR Code com o celular da loja para enviar mensagens e documentos pelo sistema."))

        risk = QLabel(RISK_TEXT)
        risk.setObjectName("infoNotice")
        risk.setWordWrap(True)
        root.addWidget(risk)
        self.accept_risk = QCheckBox("Entendi e vou usar somente para atendimento a clientes")
        root.addWidget(self.accept_risk)

        # QR Code beside the instructions: the window stays short enough for 1366×768 screens.
        body = QHBoxLayout()
        body.setSpacing(18)
        self.qr_label = QLabel("O QR Code aparecerá aqui.")
        self.qr_label.setObjectName("qrPlaceholder")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(QR_SIZE + 8, QR_SIZE + 8)
        self.qr_label.setStyleSheet("background: #FFFFFF; border: 1px solid #DCE3EE; border-radius: 12px;")
        body.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignTop)
        side = QVBoxLayout()
        side.setSpacing(10)
        steps = QLabel(
            "<b>No celular da loja:</b><br>1. Abra o WhatsApp<br>2. Toque em ⋮ ou em Configurações<br>"
            "3. Entre em <b>Aparelhos conectados</b><br>4. Toque em <b>Conectar um aparelho</b><br>"
            "5. Aponte a câmera para o QR Code"
        )
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        side.addWidget(steps)
        self.pairing_label = QLabel("")
        self.pairing_label.setObjectName("muted")
        self.pairing_label.setWordWrap(True)
        self.pairing_label.setVisible(False)
        side.addWidget(self.pairing_label)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        side.addWidget(self.status_label)
        side.addStretch(1)
        body.addLayout(side, 1)
        root.addLayout(body)

        actions = QHBoxLayout()
        self.generate_button = make_button("Gerar QR Code", "fa5s.qrcode", "primaryButton")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate)
        close = make_button("Fechar", None, "secondaryButton")
        close.clicked.connect(self.reject)
        actions.addWidget(self.generate_button)
        actions.addStretch(1)
        actions.addWidget(close)
        root.addLayout(actions)

        self.accept_risk.toggled.connect(lambda checked: self.generate_button.setEnabled(checked and not self._busy))
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._check_status)
        self._refresh = QTimer(self)
        self._refresh.setInterval(QR_REFRESH_MS)
        self._refresh.timeout.connect(self._refresh_qr)

    # ---- flow -------------------------------------------------------------
    def _set_status(self, text: str, tone: str = "") -> None:
        colors = {"ok": "#0E8A5B", "error": "#B42318", "": "#475569"}
        self.status_label.setStyleSheet(f"color: {colors.get(tone, colors[''])}; font-weight: 600;")
        self.status_label.setText(text)

    def _generate(self) -> None:
        self._refreshes = 0
        self._request_qr("Gerando QR Code…")

    def _request_qr(self, message: str) -> None:
        if self._busy:
            return
        self._busy = True
        self.generate_button.setEnabled(False)
        self._set_status(message)
        run_in_background(self, self._service.connect, self._on_qr, self._on_error)

    def _on_qr(self, result) -> None:
        self._busy = False
        status, qr, pairing = result
        if status.is_connected:
            self._finish(status)
            return
        pixmap = qr_pixmap(qr, QR_SIZE)
        if pixmap.isNull():
            self._set_status("O gateway não devolveu o QR Code. Tente gerar novamente.", "error")
            self.generate_button.setEnabled(True)
            return
        self.qr_label.setPixmap(pixmap)
        self.pairing_label.setVisible(bool(pairing))
        self.pairing_label.setText(f"Ou use o código de pareamento no celular: <b>{pairing}</b>" if pairing else "")
        self._set_status("Aguardando a leitura do QR Code…")
        self.generate_button.setText("Gerar novo QR Code")
        self.generate_button.setEnabled(True)
        self._poll.start()
        self._refresh.start()

    def _refresh_qr(self) -> None:
        self._refreshes += 1
        if self._refreshes > MAX_QR_REFRESHES:
            self._stop_timers()
            self.qr_label.clear()
            self.qr_label.setText("O QR Code expirou.")
            self._set_status("Clique em “Gerar novo QR Code” quando o celular estiver em mãos.")
            return
        self._request_qr("Atualizando o QR Code…")

    def _check_status(self) -> None:
        if self._busy:
            return
        self._busy = True
        run_in_background(self, self._service.live_status, self._on_status, self._on_poll_error)

    def _on_status(self, status: WhatsAppStatus) -> None:
        self._busy = False
        if status.is_connected:
            self._finish(status)

    def _on_poll_error(self, _message: str) -> None:
        self._busy = False  # transient: the next poll tries again

    def _on_error(self, message: str) -> None:
        self._busy = False
        self._stop_timers()
        self.generate_button.setEnabled(self.accept_risk.isChecked())
        self._set_status(message, "error")

    def _finish(self, status: WhatsAppStatus) -> None:
        self._stop_timers()
        self.connected_status = status
        self.pairing_label.setVisible(False)
        self.qr_label.clear()
        self.qr_label.setText("✓")
        self.qr_label.setStyleSheet("font-size: 80pt; color: #0E8A5B; background: #FFFFFF; border: 1px solid #DCE3EE; border-radius: 12px;")
        who = " • ".join(part for part in (status.phone_display, status.profile_name) if part)
        self._set_status(f"WhatsApp conectado{': ' + who if who else ''}.", "ok")
        self.generate_button.setVisible(False)
        QTimer.singleShot(1800, self.accept)

    def _stop_timers(self) -> None:
        self._poll.stop()
        self._refresh.stop()

    def done(self, result: int) -> None:
        self._stop_timers()
        super().done(result)


class WhatsAppSettingsCard(QFrame):
    """Status of the store WhatsApp with connect / test / disconnect actions."""

    def __init__(self, service: WhatsAppService, can_manage: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._can_manage = can_manage
        self._status = WhatsAppStatus()
        self.setObjectName("surfaceCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.status_label = QLabel("Verificando…")
        self.status_label.setObjectName("sectionTitle")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("muted")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.connect_button = make_button("Conectar WhatsApp", "fa5b.whatsapp", "primaryButton")
        self.connect_button.clicked.connect(self._connect)
        self.test_button = make_button("Enviar teste", "fa5s.paper-plane", "secondaryButton")
        self.test_button.clicked.connect(self._test)
        self.disconnect_button = make_button("Desconectar", "fa5s.unlink", "dangerButton")
        self.disconnect_button.clicked.connect(self._disconnect)
        for button in (self.connect_button, self.test_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self.disconnect_button)
        layout.addLayout(actions)
        if not service.available:
            self.status_label.setText("Disponível com login no Supabase")
            self.detail_label.setText("Na pré-visualização o WhatsApp da loja não é conectado.")
            for button in (self.connect_button, self.test_button, self.disconnect_button):
                button.setEnabled(False)
            return
        self._render()
        self.refresh()

    def refresh(self) -> None:
        run_in_background(self, self._service.live_status, self._apply, self._apply_error)

    def _apply(self, status: WhatsAppStatus) -> None:
        self._status = status
        self._render()

    def _apply_error(self, message: str) -> None:
        self._status = self._service.cached_status()
        self._render(message)

    def _render(self, error: str = "") -> None:
        status = self._status
        colors = {"connected": "#0E8A5B", "connecting": "#B7791F", "disconnected": "#64748B"}
        self.status_label.setText(f"● {status.label}")
        self.status_label.setStyleSheet(f"color: {colors.get(status.status, '#64748B')};")
        if status.is_connected:
            who = " • ".join(part for part in (status.phone_display, status.profile_name) if part)
            detail = (f"Número conectado: {who}. " if who else "") + (
                "Mensagens de pedidos, documentos de venda e contatos do CRM são enviados automaticamente.")
        elif not status.configured:
            detail = "O gateway de WhatsApp ainda não foi configurado no servidor. Fale com a AMT Sistemas."
        else:
            detail = ("Conecte o WhatsApp da loja para enviar mensagens e documentos direto pelo sistema. "
                      "Sem conexão, os envios abrem o WhatsApp no computador para você enviar manualmente.")
        if status.last_error and not status.is_connected:
            detail += f"\nÚltimo aviso: {status.last_error}"
        if error:
            detail += f"\nNão foi possível consultar o status agora: {error}"
        self.detail_label.setText(detail)
        self.connect_button.setVisible(self._can_manage and not status.is_connected)
        self.connect_button.setEnabled(status.configured)
        self.test_button.setVisible(self._can_manage and status.is_connected)
        self.disconnect_button.setVisible(self._can_manage and status.status != "disconnected")

    def _connect(self) -> None:
        dialog = ConnectWhatsAppDialog(self._service, self)
        dialog.exec()
        if dialog.connected_status is not None:
            self._apply(dialog.connected_status)
        else:
            self.refresh()

    def _test(self) -> None:
        number, accepted = QInputDialog.getText(self, "Enviar teste", "WhatsApp que vai receber o teste (com DDD):")
        if not accepted or not number.strip():
            return
        try:
            self._service.send_test(number.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Teste não enviado", str(exc))
            return
        QMessageBox.information(self, "Teste enviado", "Mensagem de teste enviada. Confira no celular informado.")

    def _disconnect(self) -> None:
        answer = QMessageBox.question(
            self, "Desconectar WhatsApp",
            "Desconectar o WhatsApp da loja do sistema?\nOs envios automáticos param até uma nova conexão.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._apply(self._service.disconnect())
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível desconectar", str(exc))
