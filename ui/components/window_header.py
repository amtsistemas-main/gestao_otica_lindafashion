"""Shared branded header utilities for application dialogs."""
from pathlib import Path
import logging

from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QBoxLayout, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QWidget

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"


def make_window_header(title_text: str, parent: QWidget) -> QFrame:
    header = QFrame(parent)
    header.setObjectName("globalBrandedHeader")
    header.setStyleSheet(
        "QFrame#globalBrandedHeader{background:#102957;border:1px solid #203D68;border-radius:8px;}"
        "QFrame#globalBrandPanel{background:#FFFFFF;border:0;border-top-left-radius:7px;border-bottom-left-radius:7px;}"
        "QLabel#globalWindowTitle{background:transparent;color:#FFFFFF;font-size:15pt;font-weight:750;padding:10px 16px;}"
    )
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    brand = QFrame(header)
    brand.setObjectName("globalBrandPanel")
    brand.setFixedWidth(112)
    brand_layout = QHBoxLayout(brand)
    brand_layout.setContentsMargins(8, 6, 8, 6)
    logo = QLabel(brand)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if LOGO_PATH.is_file():
        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(90, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    if logo.pixmap() is None or logo.pixmap().isNull():
        logo.setText("LINDA FASHION")
        logo.setStyleSheet("background:#FFFFFF;color:#2457D6;font-weight:800;")
    brand_layout.addWidget(logo)
    row.addWidget(brand)
    title = QLabel(title_text or "Ótica Linda Fashion", header)
    title.setObjectName("globalWindowTitle")
    title.setWordWrap(True)
    row.addWidget(title, 1)
    return header


class WindowHeaderInstaller(QObject):
    """Install the branded title bar on dialogs that do not already have one."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Native dialogs own their layouts and must never be modified by the global
        # title-bar installer (especially QFileDialog used by PDF export).
        if (
            event.type() != QEvent.Type.Show
            or not isinstance(watched, QDialog)
            or isinstance(watched, (QFileDialog, QMessageBox))
        ):
            return False

        dialog = watched
        if dialog.property("_global_header_installed"):
            return False

        try:
            layout = dialog.layout()
            # insertWidget() is provided by QBoxLayout, not the abstract QLayout
            # base class. Checking the type prevents exceptions escaping Qt's
            # event-filter callback when a dialog uses a grid/form layout.
            if not isinstance(layout, QBoxLayout):
                return False
            if dialog.findChild(QFrame, "windowTitleBar") or dialog.findChild(QFrame, "globalBrandedHeader"):
                dialog.setProperty("_global_header_installed", True)
                return False

            title_text = dialog.windowTitle().split(" — ")[0].split(" | ")[0].strip()
            layout.insertWidget(0, make_window_header(title_text, dialog))
            dialog.setProperty("_global_header_installed", True)
        except Exception:
            # Never let a Python exception propagate through QObject::eventFilter.
            logging.getLogger(__name__).exception(
                "Failed to install the branded header on dialog %r",
                dialog.windowTitle(),
            )
        return False


def install_window_headers(app: QApplication) -> None:
    installer = WindowHeaderInstaller(app)
    app.installEventFilter(installer)
    app.setProperty("_window_header_installer", installer)
