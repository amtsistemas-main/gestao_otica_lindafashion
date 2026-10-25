"""Sign-in window: white-label, a single centered card over a decorative backdrop."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME
from config.settings import get_settings
from core.auth_service import AuthService
from core.exceptions import ApplicationError
from ui.components.ui_kit import set_button_icon
from ui.windows.main_window import MainWindow

logger = logging.getLogger(__name__)
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"
REMEMBERED_LOGIN_KEY = "login/remembered_username"


def caps_lock_on() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
    except Exception:
        return False


class LoginBackdrop(QWidget):
    """Navy gradient with soft light glows and thin lens-like rings (purely decorative)."""

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor("#0A1D42"))
        base.setColorAt(0.55, QColor("#102957"))
        base.setColorAt(1.0, QColor("#163A78"))
        painter.fillRect(self.rect(), base)

        for cx, cy, radius, color, alpha in (
            (w * 0.88, h * 0.12, max(w, h) * 0.55, "#2165F5", 115),
            (w * 0.08, h * 0.95, max(w, h) * 0.50, "#3B82F6", 70),
            (w * 0.50, h * 0.50, max(w, h) * 0.35, "#FFFFFF", 14),
        ):
            glow = QRadialGradient(QPointF(cx, cy), radius)
            start = QColor(color)
            start.setAlpha(alpha)
            end = QColor(color)
            end.setAlpha(0)
            glow.setColorAt(0.0, start)
            glow.setColorAt(1.0, end)
            painter.fillRect(self.rect(), glow)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for cx, cy, radii in ((w * 0.86, h * 0.18, (140, 210, 290, 380)), (w * 0.12, h * 0.86, (110, 175, 250))):
            for index, radius in enumerate(radii):
                pen = QPen(QColor(255, 255, 255, 30 - index * 5))
                pen.setWidthF(1.2)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.end()


class _CapsLockWatcher(QObject):
    def __init__(self, callback, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._callback(event.type() != QEvent.Type.FocusOut)
        return False


class LoginWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} | Acesso")
        self.setMinimumSize(560, 600)
        self.resize(1080, 720)
        self._auth_service = AuthService()
        self._main_window: MainWindow | None = None
        self._settings = QSettings()

        backdrop = LoginBackdrop()
        backdrop.setObjectName("loginBackground")
        outer = QVBoxLayout(backdrop)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(420)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(3, 10, 30, 120))
        card.setGraphicsEffect(shadow)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(38, 36, 38, 34)
        layout.setSpacing(0)

        logo = QLabel()
        logo.setObjectName("loginLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                ratio = self.devicePixelRatioF()
                scaled = pixmap.scaled(int(250 * ratio), int(78 * ratio), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                scaled.setDevicePixelRatio(ratio)
                logo.setPixmap(scaled)
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText(APP_NAME)
            logo.setObjectName("loginLogoFallback")
        layout.addWidget(logo)
        layout.addSpacing(26)

        title = QLabel("Entrar")
        title.setObjectName("loginFormTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(4)
        subtitle = QLabel("Use seu usuário e senha de acesso.")
        subtitle.setObjectName("loginFormSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        username_label = QLabel("Usuário")
        username_label.setObjectName("loginFieldLabel")
        self.username_input = QLineEdit()
        self.username_input.setObjectName("loginInput")
        self.username_input.setPlaceholderText("seu.usuario")
        self.username_input.setClearButtonEnabled(True)
        self.username_input.setMinimumHeight(48)
        self.username_input.setMaxLength(160)
        self.username_input.setAccessibleName("Usuário")
        self.username_input.addAction(qta.icon("fa5s.user", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        layout.addWidget(username_label)
        layout.addSpacing(6)
        layout.addWidget(self.username_input)
        layout.addSpacing(14)

        password_label = QLabel("Senha")
        password_label.setObjectName("loginFieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginInput")
        self.password_input.setPlaceholderText("Digite sua senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(48)
        self.password_input.setAccessibleName("Senha")
        self.password_input.addAction(qta.icon("fa5s.lock", color="#8A97AB"), QLineEdit.ActionPosition.LeadingPosition)
        self._reveal = self.password_input.addAction(qta.icon("fa5s.eye", color="#8A97AB"),
                                                     QLineEdit.ActionPosition.TrailingPosition)
        self._reveal.setToolTip("Mostrar senha")
        self._reveal.triggered.connect(self._toggle_password)
        self.password_input.returnPressed.connect(self._submit)
        self.password_input.installEventFilter(_CapsLockWatcher(self._update_caps_lock, self))
        layout.addWidget(password_label)
        layout.addSpacing(6)
        layout.addWidget(self.password_input)
        layout.addSpacing(6)

        self.caps_label = QLabel("Caps Lock está ativado")
        self.caps_label.setObjectName("loginCapsLock")
        self.caps_label.setVisible(False)
        layout.addWidget(self.caps_label)
        layout.addSpacing(6)

        self.remember = QCheckBox("Lembrar meu usuário")
        self.remember.setObjectName("loginRemember")
        layout.addWidget(self.remember)
        layout.addSpacing(16)

        # The message box carries its own gap to the button and hides with it.
        self.status_box = QWidget()
        status_layout = QVBoxLayout(self.status_box)
        status_layout.setContentsMargins(0, 0, 0, 14)
        self.status_label = QLabel("")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        self.status_box.setVisible(False)
        layout.addWidget(self.status_box)

        self.login_button = QPushButton("Entrar")
        self.login_button.setObjectName("primaryButton")
        set_button_icon(self.login_button, "fa5s.sign-in-alt", 16)
        self.login_button.setMinimumHeight(50)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._submit)
        layout.addWidget(self.login_button)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        self.setCentralWidget(backdrop)

        remembered = str(self._settings.value(REMEMBERED_LOGIN_KEY, "") or "")
        if remembered:
            self.username_input.setText(remembered)
            self.remember.setChecked(True)
            self.password_input.setFocus()
        else:
            self.username_input.setFocus()

        if not get_settings().supabase_configured:
            self._show_status("Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no arquivo .env.")

    # ---- helpers ----------------------------------------------------------
    def _toggle_password(self) -> None:
        hidden = self.password_input.echoMode() == QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._reveal.setIcon(qta.icon("fa5s.eye-slash" if hidden else "fa5s.eye", color="#8A97AB"))
        self._reveal.setToolTip("Ocultar senha" if hidden else "Mostrar senha")

    def _update_caps_lock(self, focused: bool) -> None:
        self.caps_label.setVisible(focused and caps_lock_on())

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_box.setVisible(bool(message))

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.username_input, self.password_input, self.remember):
            widget.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        self.login_button.setText("Entrando…" if busy else "Entrar")

    def _submit(self) -> None:
        login = self.username_input.text().strip()
        password = self.password_input.text()
        if not login or not password:
            self._show_status("Informe seu usuário e sua senha.")
            (self.username_input if not login else self.password_input).setFocus()
            return

        self._show_status("")
        self._set_busy(True)
        QApplication.processEvents()  # show "Entrando…" before the network call blocks
        try:
            self._auth_service.sign_in(login, password)
            if self.remember.isChecked():
                self._settings.setValue(REMEMBERED_LOGIN_KEY, login)
            else:
                self._settings.remove(REMEMBERED_LOGIN_KEY)
            self._main_window = MainWindow()
            self._main_window.show()
            self.close()
        except ApplicationError as exc:
            self._show_status(str(exc))
            self.password_input.selectAll()
            self.password_input.setFocus()
        except Exception:
            logger.exception("Erro inesperado na tela de acesso.")
            self._show_status("Ocorreu um erro inesperado. Tente novamente.")
        finally:
            self._set_busy(False)
