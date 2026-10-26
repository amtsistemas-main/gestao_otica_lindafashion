"""Native PDF viewer with print, save and "send via WhatsApp" actions."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from PySide6.QtCore import QMimeData, QRect, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QPalette
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from core.phone import format_br_phone, normalize_br_whatsapp
from ui.components.background import run_in_background
from ui.components.ui_kit import make_button

ZOOM_STEP = 1.2


def documents_folder() -> Path:
    """Stable folder for documents sent to customers (the temp copy may be cleaned)."""
    base = Path.home() / "Documents"
    if not base.is_dir():
        base = Path.home()
    folder = base / "Ótica Linda Fashion" / "Documentos"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def whatsapp_number(raw: str) -> str:
    return normalize_br_whatsapp(raw)


class DocumentSender(Protocol):
    """Automatic sending through the store WhatsApp (provided by the WhatsApp module)."""

    def is_connected(self) -> bool: ...
    def needs_number(self) -> bool: ...
    def recipient_label(self) -> str: ...
    def send(self, pdf_path: str | Path, file_name: str, caption: str, number: str = "") -> tuple[bool, str]: ...


class PdfViewerDialog(QDialog):
    """Shows a generated PDF inside the app.

    ``suggested_name`` is the file name offered when saving; ``whatsapp_phone`` and
    ``whatsapp_message`` prepare the customer conversation.
    """

    def __init__(self, pdf_path: str | Path, title: str, suggested_name: str, subtitle: str = "",
                 whatsapp_phone: str = "", whatsapp_message: str = "", sender: DocumentSender | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = Path(pdf_path)
        self._suggested_name = suggested_name
        self._phone = whatsapp_phone
        self._message = whatsapp_message
        self._sender = sender
        self._auto_whatsapp = bool(sender and sender.is_connected())
        self.setWindowTitle(f"{title} — Ótica Linda Fashion")
        self.resize(1020, 900)
        self.setMinimumSize(640, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        bar_layout.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("windowTitle")
        caption = QLabel(subtitle or "Confira o documento e escolha: imprimir, salvar ou enviar ao cliente pelo WhatsApp.")
        caption.setObjectName("windowSubtitle")
        caption.setWordWrap(True)
        bar_layout.addWidget(heading)
        bar_layout.addWidget(caption)
        root.addWidget(bar)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.print_button = make_button("Imprimir", "fa5s.print", "primaryButton")
        self.print_button.clicked.connect(self._print)
        self.save_button = make_button("Salvar PDF", "fa5s.download", "secondaryButton")
        self.save_button.clicked.connect(self._save)
        self.whatsapp_button = make_button(
            "Enviar pelo WhatsApp da loja" if self._auto_whatsapp else "Enviar por WhatsApp", "fa5b.whatsapp",
            "secondaryButton")
        self.whatsapp_button.clicked.connect(self._send_whatsapp)
        for button in (self.print_button, self.save_button, self.whatsapp_button):
            tools.addWidget(button)
        tools.addStretch(1)
        zoom_out = make_button("", "fa5s.search-minus", "secondaryButton")
        zoom_out.setToolTip("Diminuir zoom")
        zoom_out.clicked.connect(lambda: self._zoom(1 / ZOOM_STEP))
        zoom_in = make_button("", "fa5s.search-plus", "secondaryButton")
        zoom_in.setToolTip("Aumentar zoom")
        zoom_in.clicked.connect(lambda: self._zoom(ZOOM_STEP))
        fit_width = make_button("Largura", "fa5s.arrows-alt-h", "secondaryButton")
        fit_width.setToolTip("Ajustar à largura da janela")
        fit_width.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        fit_page = make_button("Página inteira", "fa5s.expand", "secondaryButton")
        fit_page.setToolTip("Mostrar a página inteira")
        fit_page.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitInView))
        for button in (zoom_out, zoom_in, fit_width, fit_page):
            tools.addWidget(button)
        root.addLayout(tools)

        self.document = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setObjectName("pdfView")
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.view.setPageSpacing(16)
        # Neutral reading background around the page (QPdfView paints it with the Dark role).
        palette = self.view.palette()
        palette.setColor(QPalette.ColorRole.Dark, QColor("#E4E8EE"))
        self.view.setPalette(palette)
        root.addWidget(self.view, 1)

        footer = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        close = make_button("Fechar", None, "secondaryButton")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        error = self.document.load(str(self._path))
        if error != QPdfDocument.Error.None_:
            self.status.setText("Não foi possível abrir o PDF gerado.")
            for button in (self.print_button, self.save_button, self.whatsapp_button):
                button.setEnabled(False)
        else:
            pages = self.document.pageCount()
            self.status.setText(f"{pages} página" + ("s" if pages != 1 else "") + " • A4")

    # ---- actions ----------------------------------------------------------
    def _zoom(self, factor: float) -> None:
        current = self.view.zoomFactor()
        if self.view.zoomMode() != QPdfView.ZoomMode.Custom:
            # Start from the size currently on screen.
            page = self.document.pagePointSize(0)
            if page.width() > 0:
                current = (self.view.viewport().width() - 40) / (page.width() * self.logicalDpiX() / 72)
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.25, min(4.0, current * factor)))

    def _print(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(self._suggested_name)
        printer.setFromTo(1, self.document.pageCount())
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Imprimir documento")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.print_to(printer):
            self.status.setText("Documento enviado para a impressora.")

    def print_to(self, printer: QPrinter) -> bool:
        """Renders the pages (or the chosen range) on the printer, fitted and centered."""
        first = max(1, printer.fromPage() or 1)
        last = min(self.document.pageCount(), printer.toPage() or self.document.pageCount())
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Impressão", "Não foi possível iniciar a impressão.")
            return False
        try:
            for index in range(first - 1, last):
                if index > first - 1:
                    printer.newPage()
                target = printer.pageLayout().paintRectPixels(printer.resolution())
                page = self.document.pagePointSize(index)
                scale = min(target.width() / page.width(), target.height() / page.height())
                size = QSize(int(page.width() * scale), int(page.height() * scale))
                image = self.document.render(index, size)
                x = (target.width() - size.width()) // 2
                y = (target.height() - size.height()) // 2
                painter.drawImage(QRect(x, y, size.width(), size.height()), image)
        finally:
            painter.end()
        return True

    def _save(self) -> None:
        start = documents_folder() / self._suggested_name
        path, _ = QFileDialog.getSaveFileName(self, "Salvar PDF", str(start), "Documento PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            shutil.copyfile(self._path, path)
        except PermissionError:
            QMessageBox.critical(self, "Arquivo em uso", "Não foi possível salvar: o arquivo está aberto em outro "
                                 "programa. Feche-o ou escolha outro nome.")
            return
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return
        self.status.setText(f"PDF salvo em {path}")

    def _send_whatsapp(self) -> None:
        if self._sender is not None and self._sender.is_connected():
            self._send_whatsapp_automatic()
        else:
            self._send_whatsapp_manual()

    def _send_whatsapp_automatic(self) -> None:
        number = ""
        recipient = self._sender.recipient_label()
        if self._sender.needs_number():
            typed, accepted = QInputDialog.getText(
                self, "Enviar pelo WhatsApp da loja", "WhatsApp do cliente (com DDD):", text=self._phone or "")
            if not accepted:
                return
            number = normalize_br_whatsapp(typed)
            if not number:
                QMessageBox.warning(self, "Número inválido", "Informe o WhatsApp com DDD, por exemplo (82) 99999-1234.")
                return
            recipient = format_br_phone(number)

        confirm = QDialog(self)
        confirm.setWindowTitle("Enviar documento pelo WhatsApp")
        confirm.setMinimumWidth(520)
        layout = QVBoxLayout(confirm)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        info = QLabel(f"Enviar <b>{self._suggested_name}</b> para <b>{recipient or 'o cliente'}</b> "
                      "pelo WhatsApp da loja?<br>Confirme que o cliente solicitou este documento.")
        info.setWordWrap(True)
        layout.addWidget(info)
        message = QPlainTextEdit(self._message)
        message.setFixedHeight(110)
        layout.addWidget(message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enviar agora")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(confirm.accept)
        buttons.rejected.connect(confirm.reject)
        layout.addWidget(buttons)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        caption = message.toPlainText().strip()
        self.whatsapp_button.setEnabled(False)
        self.status.setText("Enviando pelo WhatsApp da loja…")
        run_in_background(
            self,
            lambda: self._sender.send(self._path, self._suggested_name, caption, number),
            self._on_automatic_result,
            self._on_automatic_error,
        )

    def _on_automatic_result(self, result) -> None:
        self.whatsapp_button.setEnabled(True)
        sent, message = result
        self.status.setText(message)
        if not sent:
            self._offer_manual(message)

    def _on_automatic_error(self, message: str) -> None:
        self.whatsapp_button.setEnabled(True)
        self.status.setText(message)
        self._offer_manual(message)

    def _offer_manual(self, message: str) -> None:
        answer = QMessageBox.question(
            self, "Envio automático não concluído",
            f"{message}\n\nDeseja enviar manualmente agora (abrindo o WhatsApp no computador)?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._send_whatsapp_manual()

    def _send_whatsapp_manual(self) -> None:
        phone = whatsapp_number(self._phone)
        if len(phone) < 12:
            typed, accepted = QInputDialog.getText(
                self, "Enviar por WhatsApp", "WhatsApp do cliente (com DDD):", text=self._phone or "")
            if not accepted:
                return
            phone = whatsapp_number(typed)
            if len(phone) < 12:
                QMessageBox.warning(self, "Número inválido", "Informe o WhatsApp com DDD, por exemplo (82) 99999-1234.")
                return
        # A stable copy (the generated file lives in the temp folder).
        target = documents_folder() / self._suggested_name
        try:
            shutil.copyfile(self._path, target)
        except OSError:
            target = self._path
        # The file goes to the clipboard: Ctrl+V in the chat attaches it.
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(target))])
        QGuiApplication.clipboard().setMimeData(mime)
        QDesktopServices.openUrl(QUrl("https://wa.me/" + phone + "?text=" + quote(self._message)))
        if sys.platform == "win32":
            # Also shows the file selected in Explorer, ready to drag into the chat.
            subprocess.Popen(["explorer", "/select,", str(target)])  # noqa: S603,S607 - fixed system command
        self.status.setText("Conversa aberta com a mensagem pronta. O PDF foi copiado: na conversa, pressione Ctrl+V "
                            "(ou arraste o arquivo) e envie.")
        QMessageBox.information(
            self, "Enviar por WhatsApp",
            "A conversa com o cliente foi aberta com a mensagem pronta.\n\n"
            "O PDF já está copiado: clique na conversa, pressione Ctrl+V para anexar e envie.\n"
            "Se preferir, arraste o arquivo da pasta que foi aberta.\n\n"
            "O WhatsApp não permite que o sistema envie o arquivo sozinho.",
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.document.close()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self.document.close()
        super().done(result)
