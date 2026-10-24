"""Main application shell with a premium SaaS navigation layout."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME, WINDOW_TITLE
from core.auth_service import AuthService
from core.session_manager import session_manager
from modules.products.page import ProductsPage
from ui.pages.dashboard_page import DashboardPage

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"

NAV_ITEMS = [
    ("Visão geral", "VG", None),
    ("Produtos", "PR", "Produtos"),
    ("Estoque", "ES", "Estoque"),
    ("Fornecedores", "FO", "Fornecedores"),
    ("Financeiro", "FI", "Financeiro"),
    ("Relatórios", "RE", "Relatórios"),
    ("Configurações", "CO", "Configurações"),
]


class MainWindow(QMainWindow):
    def __init__(self, preview_mode: bool = False) -> None:
        super().__init__()
        self._preview_mode = preview_mode
        self.setWindowTitle(f"{WINDOW_TITLE} — Pré-visualização" if preview_mode else WINDOW_TITLE)
        self.resize(1360, 900)
        self.setMinimumSize(1000, 680)
        self._auth_service = AuthService()
        self._products_window: ProductsPage | None = None
        self._nav_buttons: dict[str, QPushButton] = {}

        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("appSidebar")
        sidebar.setFixedWidth(226)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 22, 18, 18)
        side_layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        46, 46,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText("LF")
            logo.setObjectName("logoFallback")
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(2)
        brand_name = QLabel(APP_NAME)
        brand_name.setObjectName("sidebarBrand")
        brand_name.setWordWrap(True)
        brand_subtitle = QLabel("GESTÃO INTELIGENTE")
        brand_subtitle.setObjectName("sidebarEyebrow")
        brand_copy.addWidget(brand_name)
        brand_copy.addWidget(brand_subtitle)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_copy, 1)
        side_layout.addLayout(brand_row)

        side_layout.addSpacing(26)
        nav_label = QLabel("MENU PRINCIPAL")
        nav_label.setObjectName("sidebarSection")
        side_layout.addWidget(nav_label)

        for label, abbreviation, module in NAV_ITEMS:
            button = QPushButton(f"  {abbreviation}     {label}")
            button.setObjectName("navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.setMinimumHeight(43)
            button.setChecked(module is None)
            button.clicked.connect(
                lambda checked=False, selected=module: self._navigate(selected)
            )
            self._nav_buttons[label] = button
            side_layout.addWidget(button)

        side_layout.addStretch()

        workspace = QFrame()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(76)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(28, 10, 28, 10)
        topbar_layout.setSpacing(12)

        context = QVBoxLayout()
        context.setSpacing(2)
        context_title = QLabel("Painel de gestão")
        context_title.setObjectName("topbarTitle")
        context_subtitle = QLabel(
            "Visão unificada da Ótica Linda Fashion"
            if not preview_mode
            else "Ambiente de demonstração • sem conexão com o banco"
        )
        context_subtitle.setObjectName("muted")
        context.addWidget(context_title)
        context.addWidget(context_subtitle)
        topbar_layout.addLayout(context)
        topbar_layout.addStretch()

        if preview_mode:
            account_label = QLabel("PRÉ-VISUALIZAÇÃO")
            account_label.setObjectName("previewBadge")
            topbar_layout.addWidget(account_label)
        else:
            user_email = session_manager.current.email if session_manager.current else ""
            account_label = QLabel(user_email)
            account_label.setObjectName("accountLabel")
            account_label.setToolTip(user_email)
            topbar_layout.addWidget(account_label)
            logout_button = QPushButton("Sair")
            logout_button.setObjectName("logoutButton")
            logout_button.clicked.connect(self._logout)
            topbar_layout.addWidget(logout_button)

        workspace_layout.addWidget(topbar)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("mainScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._dashboard = DashboardPage(preview_mode=preview_mode)
        self._dashboard.setContentsMargins(0, 0, 0, 0)
        self._dashboard.module_requested.connect(self._open_module)
        self._scroll.setWidget(self._dashboard)
        scroll_host = QWidget()
        scroll_layout = QVBoxLayout(scroll_host)
        scroll_layout.setContentsMargins(28, 26, 28, 22)
        scroll_layout.addWidget(self._scroll)
        workspace_layout.addWidget(scroll_host, 1)

        side_footer = QLabel("AMT SISTEMAS  •  DESKTOP")
        side_footer.setObjectName("sidebarFooter")
        side_layout.addWidget(side_footer)

        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(workspace, 1)
        self.setCentralWidget(shell)

        status = QStatusBar()
        status.showMessage(
            "Pré-visualização local • os dados não são persistidos"
            if preview_mode
            else "Sistema pronto • módulos em evolução"
        )
        self.setStatusBar(status)

    def _navigate(self, module: str | None) -> None:
        for label, _abbreviation, target in NAV_ITEMS:
            button = self._nav_buttons[label]
            button.setChecked(target == module)
        if module is None:
            self._scroll.verticalScrollBar().setValue(0)
            return
        self._open_module(module)

    def _open_module(self, module: str) -> None:
        for label, _abbreviation, target in NAV_ITEMS:
            self._nav_buttons[label].setChecked(target == module)
        if module == "Produtos":
            try:
                if self._products_window is None:
                    self._products_window = ProductsPage(
                        preview_mode=self._preview_mode,
                        parent=self,
                    )
                self._products_window.exec()
            except Exception as exc:
                QMessageBox.critical(self, "Não foi possível abrir Produtos", str(exc))
            finally:
                self._nav_buttons["Visão geral"].setChecked(True)
            return

        QMessageBox.information(
            self,
            module,
            f"O módulo {module.lower()} será implementado na próxima etapa.",
        )
        self._nav_buttons["Visão geral"].setChecked(True)

    def _logout(self) -> None:
        self._auth_service.sign_out()
        self.close()
        from ui.windows.login_window import LoginWindow

        self._login_window = LoginWindow()
        self._login_window.show()
