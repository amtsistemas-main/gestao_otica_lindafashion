"""Shared branded header and automatic polish for application dialogs."""
from pathlib import Path
import logging

from PySide6.QtCore import QObject, QRect, QSize, Qt, QEvent
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QBoxLayout, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QTableWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ui.components.enter_guard import install_enter_guard

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
        # Text buttons never shrink below their label (no clipped captions).
        if button.text() and not button.property("_min_width_fixed"):
            button.setProperty("_min_width_fixed", True)
            button.setMinimumWidth(max(button.minimumWidth(), button.sizeHint().width()))
    # Multi-line inputs keep at least three visible lines instead of collapsing to one.
    for editor in [*dialog.findChildren(QTextEdit), *dialog.findChildren(QPlainTextEdit)]:
        lines = min(editor.maximumHeight(), editor.fontMetrics().lineSpacing() * 3 + 20)
        if not editor.isReadOnly() and editor.minimumHeight() < lines:
            editor.setMinimumHeight(lines)
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


# Window frame and title bar drawn by the OS around the client area.
_FRAME_W, _FRAME_H = 16, 48
_FIXED_TOP = {"windowTitleBar", "globalBrandedHeader"}


def available_area(window: QWidget) -> QRect:
    """Usable screen area (taskbar excluded) for the window's screen."""
    screen = window.screen() or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 1366, 728)


def _wrap_content_in_scroll(dialog: QDialog) -> bool:
    """Moves the middle of a vertical dialog layout into a scroll area.

    The title bar stays on top and the trailing buttons stay visible; only the content
    scrolls. Used when the content cannot fit the screen.
    """
    layout = dialog.layout()
    if not isinstance(layout, QBoxLayout) or layout.direction() not in (
        QBoxLayout.Direction.TopToBottom, QBoxLayout.Direction.BottomToTop
    ) or dialog.property("_scroll_wrapped"):
        return False
    count = layout.count()
    stretches = [layout.stretch(index) for index in range(count)]
    first = 0
    while first < count and isinstance(layout.itemAt(first).widget(), QFrame) \
            and layout.itemAt(first).widget().objectName() in _FIXED_TOP:
        first += 1
    last = count
    if last > first:
        tail = layout.itemAt(last - 1)
        tail_widget = tail.widget()
        tail_layout = tail.layout()
        is_buttons = isinstance(tail_widget, QDialogButtonBox) or (
            isinstance(tail_widget, QPushButton)
        ) or (
            tail_layout is not None and not any(
                not isinstance(tail_layout.itemAt(i).widget(), (QPushButton, type(None)))
                for i in range(tail_layout.count())
            )
        )
        if is_buttons:
            last -= 1
    if last <= first:
        return False
    content = QWidget()
    content.setObjectName("scrollContent")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 8, 0)
    content_layout.setSpacing(layout.spacing())
    has_stretch = False
    for stretch in stretches[first:last]:
        # takeAt hands the item over; read what it holds before anything else touches it.
        item = layout.takeAt(first)
        widget, child, spacer = item.widget(), item.layout(), item.spacerItem()
        if widget is not None:
            content_layout.addWidget(widget, stretch)
        elif child is not None:
            child.setParent(None)
            content_layout.addLayout(child, stretch)
        elif spacer is not None:
            if spacer.expandingDirections() & Qt.Orientation.Vertical:
                content_layout.addStretch(max(stretch, 1))
            else:
                content_layout.addSpacing(spacer.sizeHint().height())
        has_stretch = has_stretch or stretch > 0
    if not has_stretch:
        content_layout.addStretch(1)
    scroll = QScrollArea(dialog)
    scroll.setObjectName("dialogScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    # Vertical scrolling only: the area reserves the content width plus the scrollbar.
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    scroll.setMinimumWidth(content.minimumSizeHint().width() + scroll.verticalScrollBar().sizeHint().width() + 4)
    layout.insertWidget(first, scroll, 1)
    dialog.setProperty("_scroll_wrapped", True)
    return True


def fit_to_screen(window: QWidget) -> None:
    """Keeps a top-level window entirely on screen, without clipped content.

    Runs once per window: limits size and minimum size to the usable screen area, grows
    the window to its ideal size when there is room (no squeezed fields) and, when the
    content alone is taller/wider than the screen, makes the content scroll.
    """
    if window.property("_fitted_to_screen") or not window.isWindow():
        return
    window.setProperty("_fitted_to_screen", True)
    area = available_area(window)
    max_w, max_h = max(320, area.width() - _FRAME_W), max(240, area.height() - _FRAME_H)
    if isinstance(window, QDialog):
        hint = window.minimumSizeHint()
        if (hint.height() > max_h or hint.width() > max_w) and _wrap_content_in_scroll(window):
            window.layout().activate()
    # An explicit minimum smaller than the layout's real minimum would clip widgets;
    # a wrapped dialog keeps a readable width for its title bar and fields.
    hint = window.minimumSizeHint()
    wrapped = bool(window.property("_scroll_wrapped"))
    floor_w, floor_h = (min(560, max_w), min(440, max_h)) if wrapped else (0, 0)
    window.setMinimumSize(
        min(max(window.minimumWidth(), hint.width(), floor_w), max_w),
        min(max(window.minimumHeight(), hint.height(), floor_h), max_h),
    )
    # QWidget.size/resize explicitly: some dialogs have a field attribute named "size".
    current = QWidget.size(window)
    ideal = window.sizeHint().expandedTo(current)
    target = QSize(min(ideal.width(), max_w), min(ideal.height(), max_h))
    if target != current:
        QWidget.resize(window, target)
    frame = window.frameGeometry()
    parent = window.parentWidget()
    center = parent.window().frameGeometry().center() if parent is not None and parent.isVisible() else area.center()
    left = min(max(area.left(), center.x() - frame.width() // 2), area.right() - frame.width() + 1)
    top = min(max(area.top(), center.y() - frame.height() // 2), area.bottom() - frame.height() + 1)
    window.move(max(area.left(), left), max(area.top(), top))


class WindowHeaderInstaller(QObject):
    """Install the branded title bar and shared polish on application dialogs."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QMainWindow):
            try:
                fit_to_screen(watched)
            except Exception:
                logging.getLogger(__name__).exception("Failed to fit window %r", watched.windowTitle())
            return False
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
            if isinstance(dialog, QMessageBox):
                return False
            self._install_header(dialog)
            # Last step: the header above also counts toward the height that must fit.
            fit_to_screen(dialog)
        except Exception:
            # Never let a Python exception propagate through QObject::eventFilter.
            logging.getLogger(__name__).exception(
                "Failed to polish dialog %r",
                dialog.windowTitle(),
            )
        return False

    @staticmethod
    def _install_header(dialog: QDialog) -> None:
        if dialog.property("_global_header_installed"):
            return
        layout = dialog.layout()
        # insertWidget() is provided by QBoxLayout, not the abstract QLayout
        # base class. Checking the type prevents exceptions escaping Qt's
        # event-filter callback when a dialog uses a grid/form layout.
        if not isinstance(layout, QBoxLayout):
            return
        dialog.setProperty("_global_header_installed", True)
        if dialog.findChild(QFrame, "windowTitleBar") or dialog.findChild(QFrame, "globalBrandedHeader"):
            return
        title_text = dialog.windowTitle().split(" — ")[0].split(" | ")[0].strip()
        layout.insertWidget(0, make_window_header(title_text, dialog))


def install_window_headers(app: QApplication) -> None:
    installer = WindowHeaderInstaller(app)
    app.installEventFilter(installer)
    app.setProperty("_window_header_installer", installer)
    install_enter_guard(app)
