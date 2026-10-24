"""Premium light sign-in window for Ótica Linda Fashion."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME, APP_SUBTITLE
from config.settings import get_settings
from core.auth_service import AuthService
from core.exceptions import ApplicationError
from ui.windows.main_window import MainWindow

logger = logging.getLogger(__name__)
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"


class LoginWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} | Acesso")
        self.setMinimumSize(900, 620)
        self.resize(1080, 700)
        self._auth_service = AuthService()
        self._main_window: MainWindow | None = None

        root = QWidget()
        root.setObjectName("loginBackground")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(18)

        # Branded welcome panel
        brand_panel = QFrame()
        brand_panel.setObjectName("loginBrandPanel")
        brand_panel.setMinimumWidth(300)
        brand_panel.setMaximumWidth(410)
        brand_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        brand_layout = QVBoxLayout(brand_panel)
        brand_layout.setContentsMargins(30, 30, 30, 30)
        brand_layout.setSpacing(16)

        logo = QLabel()
        logo.setObjectName("loginLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(120)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaled(
                    245, 125,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText("ÓTICA\nLINDA FASHION")
            logo.setObjectName("loginLogoFallback")
        brand_layout.addWidget(logo)
        brand_layout.addSpacing(8)

        brand_eyebrow = QLabel("GESTÃO INTELIGENTE")
        brand_eyebrow.setObjectName("loginEyebrow")
        brand_title = QLabel("Sua ótica,\nmais organizada.")
        brand_title.setObjectName("loginBrandTitle")
        brand_title.setWordWrap(True)
        brand_description = QLabel(
            "Uma visão mais clara do seu negócio começa com uma gestão simples, "
            "confiável e feita para crescer com você."
        )
        brand_description.setObjectName("loginBrandDescription")
        brand_description.setWordWrap(True)
        brand_layout.addWidget(brand_eyebrow)
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_description)
        brand_layout.addStretch(1)

        feature = QFrame()
        feature.setObjectName("loginFeature")
        feature_layout = QVBoxLayout(feature)
        feature_layout.setContentsMargins(16, 16, 16, 16)
        feature_layout.setSpacing(6)
        feature_title = QLabel("Tudo sob controle")
        feature_title.setObjectName("loginFeatureTitle")
        feature_text = QLabel("Produtos • Estoque • Financeiro • Relatórios")
        feature_text.setObjectName("loginFeatureText")
        feature_text.setWordWrap(True)
        feature_layout.addWidget(feature_title)
        feature_layout.addWidget(feature_text)
        brand_layout.addWidget(feature)

        brand_footer = QLabel("ÓTICA LINDA FASHION  •  AMT SISTEMAS")
        brand_footer.setObjectName("loginBrandFooter")
        brand_layout.addWidget(brand_footer)

        # Sign-in form panel
        form_host = QFrame()
        form_host.setObjectName("loginFormHost")
        form_layout = QVBoxLayout(form_host)
        form_layout.setContentsMargins(34, 26, 34, 26)
        form_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setMaximumWidth(470)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(12)

        eyebrow = QLabel("BEM-VINDO DE VOLTA")
        eyebrow.setObjectName("loginFormEyebrow")
        title = QLabel("Acesse sua conta")
        title.setObjectName("loginFormTitle")
        subtitle = QLabel("Entre para continuar a gestão da sua ótica.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        card_layout.addWidget(eyebrow)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(12)

        email_label = QLabel("E-mail")
        email_label.setObjectName("fieldLabel")
        self.email_input = QLineEdit()
        self.email_input.setObjectName("loginInput")
        self.email_input.setPlaceholderText("seu@email.com")
        self.email_input.setClearButtonEnabled(True)
        self.email_input.setMinimumHeight(46)
        self.email_input.setAccessibleName("E-mail")

        password_label = QLabel("Senha")
        password_label.setObjectName("fieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginInput")
        self.password_input.setPlaceholderText("Digite sua senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(46)
        self.password_input.setAccessibleName("Senha")
        self.password_input.returnPressed.connect(self._submit)

        self.status_label = QLabel("")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setWordWrap(True)

        self.login_button = QPushButton("Entrar na plataforma   →")
        self.login_button.setObjectName("primaryButton")
        self.login_button.setMinimumHeight(48)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._submit)

        card_layout.addWidget(email_label)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(2)
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.login_button)

        security_note = QLabel("Acesso protegido • Conexão com o Supabase")
        security_note.setObjectName("loginSecurityNote")
        security_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(security_note)

        form_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        form_layout.addStretch(1)
        root_layout.addWidget(brand_panel, 4)
        root_layout.addWidget(form_host, 5)
        self.setCentralWidget(root)

        settings = get_settings()
        if not settings.supabase_configured:
            self.status_label.setText(
                "Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no arquivo .env."
            )

    def _submit(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            self.status_label.setText("Informe seu e-mail e sua senha.")
            return

        self.login_button.setEnabled(False)
        self.login_button.setText("Validando acesso…")
        self.status_label.setText("")
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
            self.login_button.setText("Entrar na plataforma   →")
