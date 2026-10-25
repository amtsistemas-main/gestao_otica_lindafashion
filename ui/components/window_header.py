"""Shared branded header and automatic polish for application dialogs."""
from pathlib import Path
import logging

from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QBoxLayout, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QWidget,
)

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"

_ACCEPT_ROLES = {
    QDialogButtonBox.ButtonRole.AcceptRole,
    QDialogButtonBox.ButtonRole.YesRole,
    QDialogButtonBox.ButtonRole.ApplyRole,
}


def make_window_header(title_text: str, parent: QWidget) -> QFrame:
    header = QFrame(parent)
    header.setObjectName("globalBrandedHeader")
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    brand = QFrame(header)
    brand.setObjectName("globalBrandPanel")
    brand.setFixedWidth(112)
    brand_layout = QHBoxLayout(brand)
    brand_layout.setContentsMargins(10, 6, 10, 6)
    logo = QLabel(brand)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if LOGO_PATH.is_file():
        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(90, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    if logo.pixmap() is None or logo.pixmap().isNull():
        logo.setText("LINDA FASHION")
        logo.setObjectName("globalBrandFallback")
    brand_layout.addWidget(logo)
    row.addWidget(brand)
    title = QLabel(title_text or "Ótica Linda Fashion", header)
    title.setObjectName("globalWindowTitle")
    title.setWordWrap(True)
    row.addWidget(title, 1)
    return header


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def _align_form_labels(dialog: QDialog) -> None:
    """Center form labels on their fields and share one label column per dialog."""
    if dialog.property("_forms_aligned"):
        return
    dialog.setProperty("_forms_aligned", True)
    labels: list[QLabel] = []
    for form in dialog.findChildren(QFormLayout):
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(max(form.horizontalSpacing(), 16))
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            widget = item.widget() if item is not None else None
            if not isinstance(widget, QLabel):
                continue
            labels.append(widget)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            field = field_item.widget() if field_item is not None else None
            # Single-line fields: give the label the field height so its text sits centered.
            if field is not None and field.sizeHint().height() <= 60:
                widget.setMinimumHeight(field.sizeHint().height())
                widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if len(labels) > 1:
        width = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(width)
    for spin in dialog.findChildren(QAbstractSpinBox):
        if isinstance(spin, (QSpinBox, QDoubleSpinBox)) and spin.objectName() != "measureInput":
            editor = spin.findChild(QLineEdit)
            if editor is not None:
                editor.setTextMargins(8, 0, 0, 0)


def polish_dialog(dialog: QDialog) -> None:
    """Apply the shared interaction standard to a dialog's widgets.

    Confirmation buttons become primary actions, every button shows a hand cursor
    and data tables follow one clean, consistent presentation.
    """
    for box in dialog.findChildren(QDialogButtonBox):
        for button in box.buttons():
            if not button.objectName() and box.buttonRole(button) in _ACCEPT_ROLES:
                button.setObjectName("primaryButton")
                _repolish(button)
    if isinstance(dialog, QMessageBox):
        for button in dialog.buttons():
            if not button.objectName() and dialog.buttonRole(button) in _ACCEPT_ROLES:
                button.setObjectName("primaryButton")
                _repolish(button)
    for button in dialog.findChildren(QPushButton):
        if button.isEnabled():
            button.setCursor(Qt.CursorShape.PointingHandCursor)
    _align_form_labels(dialog)
    for table in dialog.findChildren(QTableWidget):
        if table.property("_polished"):
            continue
        table.setProperty("_polished", True)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(max(42, table.verticalHeader().defaultSectionSize()))
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.horizontalHeader().setMinimumHeight(40)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setFrameShape(QFrame.Shape.StyledPanel)


class WindowHeaderInstaller(QObject):
    """Install the branded title bar and shared polish on application dialogs."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Native file dialogs own their layouts and must never be modified by the
        # global installer (especially QFileDialog used by PDF export).
        if (
            event.type() != QEvent.Type.Show
            or not isinstance(watched, QDialog)
            or isinstance(watched, QFileDialog)
        ):
            return False

        dialog = watched
        try:
            polish_dialog(dialog)
            if isinstance(dialog, QMessageBox) or dialog.property("_global_header_installed"):
                return False
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
                "Failed to polish dialog %r",
                dialog.windowTitle(),
            )
        return False


def install_window_headers(app: QApplication) -> None:
    installer = WindowHeaderInstaller(app)
    app.installEventFilter(installer)
    app.setProperty("_window_header_installer", installer)
