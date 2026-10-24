"""Email/password sign-in window."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME, APP_SUBTITLE
from config.settings import get_settings
from core.auth_service import AuthService
from core.exceptions import ApplicationError
from ui.windows.main_window import MainWindow

logger = logging.getLogger(__name__)


class LoginWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} | Acesso")
        self.setMinimumSize(480, 580)
        self.resize(520, 620)
        self._auth_service = AuthService()
        self._main_window: MainWindow | None = None

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(34, 34, 34, 34)
        root_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(14)

        brand = QLabel("LF")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(66, 66)
        brand.setStyleSheet(
            "background:#172c52; color:#ffffff; border-radius:18px;"
            "font-size:22pt; font-weight:800;"
        )
        brand_row = QHBoxLayout()
        brand_row.addStretch()
        brand_row.addWidget(brand)
        brand_row.addStretch()

        title = QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("seu@email.com")
        self.email_input.setClearButtonEnabled(True)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Sua senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._submit)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)

        self.login_button = QPushButton("Entrar")
        self.login_button.setObjectName("primaryButton")
        self.login_button.setMinimumHeight(46)
        self.login_button.clicked.connect(self._submit)

        card_layout.addLayout(brand_row)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)
        card_layout.addWidget(QLabel("E-mail"))
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(QLabel("Senha"))
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.login_button)

        root_layout.addWidget(card)
        root_layout.addStretch(1)

        footer = QLabel("Acesso seguro • Dados online")
        footer.setObjectName("muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(footer)
        self.setCentralWidget(root)

        settings = get_settings()
        if not settings.supabase_configured:
            self.status_label.setText(
                "Configure o Supabase no arquivo .env para habilitar o acesso."
            )

    def _submit(self) -> None:
        email = self.email_input.text()
        password = self.password_input.text()
        self.login_button.setEnabled(False)
        self.status_label.setText("Validando acesso…")
        try:
            self._auth_service.sign_in(email, password)
            self._main_window = MainWindow()
            self._main_window.show()
            self.close()
        except ApplicationError as exc:
            self.status_label.setText(str(exc))
        except Exception:
            logger.exception("Erro inesperado na tela de acesso.")
            self.status_label.setText("Ocorreu um erro inesperado. Tente novamente.")
        finally:
            self.login_button.setEnabled(True)
