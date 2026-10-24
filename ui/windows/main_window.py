"""Main application shell with a premium SaaS navigation layout."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME, WINDOW_TITLE
from core.auth_service import AuthService
from core.session_manager import session_manager
from modules.products.page import ProductsPage
from modules.inventory.page import InventoryPage
from modules.suppliers.page import SuppliersPage
from modules.finance.page import FinancePage
from modules.customers.page import CustomersPage
from ui.pages.dashboard_page import DashboardPage
from ui.components.ai_results_panel import BusinessAnalysisPanel
from core.ai_analysis_service import AIAnalysisWorker

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"

NAV_ITEMS = [
    ("Visão geral", "fa5s.home", None),
    ("Produtos", "fa5s.glasses", "Produtos"),
    ("Clientes", "fa5s.users", "Clientes"),
    ("Estoque", "fa5s.warehouse", "Estoque"),
    ("Fornecedores", "fa5s.truck", "Fornecedores"),
    ("Financeiro", "fa5s.wallet", "Financeiro"),
    ("Relatórios", "fa5s.chart-bar", "Relatórios"),
    ("Análises", "fa5s.chart-line", "Análises"),
    ("Configurações", "fa5s.cog", "Configurações"),
]


class MainWindow(QMainWindow):
    def __init__(self, preview_mode: bool = False) -> None:
        super().__init__()
        self._preview_mode = preview_mode
        self.setWindowTitle(f"{WINDOW_TITLE} — Pré-visualização" if preview_mode else WINDOW_TITLE)
        self.resize(1440, 920)
        self.setMinimumSize(1120, 720)
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
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 22, 18, 18)
        side_layout.setSpacing(8)

        # The transparent brand artwork is the visual anchor of the sidebar.
        logo = QLabel()
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(112)
        logo.setMaximumHeight(124)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        188, 118,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText("ÓTICA\nLINDA FASHION")
            logo.setObjectName("logoFallback")
        side_layout.addWidget(logo)
        brand_subtitle = QLabel("VISÃO  •  ESTILO  •  VOCÊ")
        brand_subtitle.setObjectName("sidebarEyebrow")
        brand_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(brand_subtitle)

        side_layout.addSpacing(26)
        nav_label = QLabel("MENU PRINCIPAL")
        nav_label.setObjectName("sidebarSection")
        side_layout.addWidget(nav_label)

        for label, icon_name, module in NAV_ITEMS:
            button = QPushButton(label)
            button.setIcon(qta.icon(icon_name, color="#FFFFFF" if module is None else "#D5E1F5"))
            button.setIconSize(QSize(18, 18))
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
        topbar.setFixedHeight(56)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(20, 8, 24, 8)
        topbar_layout.setSpacing(12)

        menu_button = QPushButton()
        menu_button.setIcon(qta.icon("fa5s.bars", color="#102957"))
        menu_button.setIconSize(QSize(17, 17))
        menu_button.setObjectName("topbarIconButton")
        menu_button.setFixedSize(36, 36)
        menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_button.clicked.connect(lambda: self._scroll.verticalScrollBar().setValue(0))
        topbar_layout.addWidget(menu_button)

        search_box = QLineEdit()
        search_box.setObjectName("dashboardSearch")
        search_box.setPlaceholderText("Buscar no sistema...")
        search_box.addAction(qta.icon("fa5s.search", color="#7A8EAF"), QLineEdit.ActionPosition.LeadingPosition)
        search_box.setClearButtonEnabled(True)
        search_box.setMinimumHeight(40)
        search_box.setMaximumWidth(360)
        topbar_layout.addWidget(search_box, 1)
        topbar_layout.addStretch()

        notifications = QPushButton()
        notifications.setIcon(qta.icon("fa5s.bell", color="#102957"))
        notifications.setIconSize(QSize(18, 18))
        notifications.setObjectName("topbarIconButton")
        notifications.setFixedSize(38, 38)
        notifications.setToolTip("Notificações")
        topbar_layout.addWidget(notifications)

        avatar = QLabel()
        avatar.setObjectName("accountAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setPixmap(qta.icon("fa5s.user", color="#102957").pixmap(19, 19))
        avatar.setFixedSize(40, 40)
        topbar_layout.addWidget(avatar)

        profile_box = QVBoxLayout()
        profile_box.setSpacing(1)
        if preview_mode:
            profile_name, profile_role = "Ana Silva", "Administrador"
        else:
            profile_name = session_manager.current.email if session_manager.current else "Usuário"
            profile_role = "Conta conectada"
        profile_name_label = QLabel(profile_name)
        profile_name_label.setObjectName("profileName")
        profile_box.addWidget(profile_name_label)
        role_label = QLabel(profile_role)
        role_label.setObjectName("profileRole")
        profile_box.addWidget(role_label)
        topbar_layout.addLayout(profile_box)

        profile_menu = QPushButton()
        profile_menu.setIcon(qta.icon("fa5s.chevron-down", color="#102957"))
        profile_menu.setIconSize(QSize(11, 11))
        profile_menu.setObjectName("topbarIconButton")
        profile_menu.setFixedSize(28, 36)
        profile_menu.setToolTip("Sair da conta" if not preview_mode else "Perfil de demonstração")
        if not preview_mode:
            profile_menu.clicked.connect(self._logout)
        topbar_layout.addWidget(profile_menu)

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
        scroll_layout.setContentsMargins(20, 20, 20, 16)
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
        if module == "Análises":
            self._open_business_analysis()
            self._nav_buttons["Visão geral"].setChecked(True)
            return

        if module in ("Produtos", "Estoque", "Fornecedores", "Financeiro", "Clientes"):
            try:
                if module == "Financeiro":
                    finance_window = FinancePage(preview_mode=self._preview_mode, parent=self)
                    finance_window.exec()
                elif module == "Produtos":
                    if self._products_window is None:
                        self._products_window = ProductsPage(
                            preview_mode=self._preview_mode,
                            parent=self,
                        )
                    self._products_window.exec()
                elif module == "Clientes":
                    customers_window = CustomersPage(
                        preview_mode=self._preview_mode,
                        parent=self,
                    )
                    customers_window.exec()
                elif module == "Estoque":
                    inventory_window = InventoryPage(
                        preview_mode=self._preview_mode,
                        parent=self,
                    )
                    inventory_window.exec()
                else:
                    suppliers_window = SuppliersPage(
                        preview_mode=self._preview_mode,
                        parent=self,
                    )
                    suppliers_window.exec()
            except Exception as exc:
                QMessageBox.critical(self, f"Não foi possível abrir {module}", str(exc))
            finally:
                self._nav_buttons["Visão geral"].setChecked(True)
            return

        QMessageBox.information(
            self,
            module,
            f"O módulo {module.lower()} será implementado na próxima etapa.",
        )
        self._nav_buttons["Visão geral"].setChecked(True)

    def _open_business_analysis(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Análises da operação — Ótica Linda Fashion")
        dialog.resize(1040, 780)
        dialog.setMinimumSize(820, 620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        panel = BusinessAnalysisPanel(dialog)
        panel.generate_requested.connect(
            lambda request: self._analysis_generation_unavailable(panel, request)
        )
        panel.regenerate_requested.connect(
            lambda request: self._analysis_generation_unavailable(panel, request)
        )
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        layout.addWidget(scroll)
        dialog.exec()

    @staticmethod
    def _analysis_generation_unavailable(panel: BusinessAnalysisPanel, request: dict) -> None:
        panel.set_loading(False)
        QMessageBox.information(
            panel,
            "Análise ainda não disponível",
            "A interface está pronta, mas a análise local ainda não foi conectada aos dados necessários. Nenhum serviço externo de IA será utilizado.\n\nDetalhes: "
            "um serviço de IA conectado. Nenhuma análise foi simulada. "
            "A solicitação selecionada foi: "
            f"{request.get('analysis_label', 'Análise')} — {request.get('period_label', 'período')}.",
        )

    def _logout(self) -> None:
        self._auth_service.sign_out()
        self.close()
        from ui.windows.login_window import LoginWindow

        self._login_window = LoginWindow()
        self._login_window.show()
