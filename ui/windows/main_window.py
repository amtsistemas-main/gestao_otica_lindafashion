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
from modules.sales.page import SalesPage
from modules.lab_orders.page import LabOrdersPage
from modules.crm.page import CrmPage
from modules.analytics.page import AnalyticsPage
from modules.settings.page import SettingsDialog
from ui.pages.dashboard_page import DashboardPage
from ui.components.ai_results_panel import BusinessAnalysisPanel
from core.ai_analysis_service import AIAnalysisWorker

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"

NAV_ITEMS = [
    ("Visão geral", "fa5s.home", None),
    ("Vendas / PDV", "fa5s.cash-register", "Vendas"),
    ("Pedidos", "fa5s.clipboard-list", "Pedidos"),
    ("Clientes", "fa5s.users", "Clientes"),
    ("Relacionamento", "fa5s.heart", "Relacionamento"),
    ("Produtos", "fa5s.glasses", "Produtos"),
    ("Estoque", "fa5s.warehouse", "Estoque"),
    ("Fornecedores", "fa5s.truck", "Fornecedores"),
    ("Financeiro", "fa5s.wallet", "Financeiro"),
    ("Indicadores", "fa5s.chart-bar", "Indicadores"),
    ("Análises", "fa5s.chart-line", "Análises"),
    ("Configurações", "fa5s.cog", "Configurações"),
]

# Module windows opened from the navigation; each receives preview_mode and parent.
MODULE_WINDOWS = {
    "Vendas": SalesPage,
    "Pedidos": LabOrdersPage,
    "Clientes": CustomersPage,
    "Relacionamento": CrmPage,
    "Estoque": InventoryPage,
    "Fornecedores": SuppliersPage,
    "Financeiro": FinancePage,
    "Indicadores": AnalyticsPage,
    "Configurações": SettingsDialog,
}


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
        self._sidebar_collapsed = False

        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("appSidebar")
        self._sidebar = sidebar
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        self._sidebar_layout = side_layout
        side_layout.setContentsMargins(18, 22, 18, 18)
        side_layout.setSpacing(4)

        # The transparent brand artwork is the visual anchor of the sidebar.
        logo = QLabel()
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(78)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        176, 62,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText("ÓTICA\nLINDA FASHION")
            logo.setObjectName("logoFallback")
        self._sidebar_logo = logo
        side_layout.addWidget(logo)
        brand_subtitle = QLabel("VISÃO  •  ESTILO  •  VOCÊ")
        brand_subtitle.setObjectName("sidebarEyebrow")
        brand_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._brand_subtitle = brand_subtitle
        side_layout.addWidget(brand_subtitle)

        side_layout.addSpacing(18)
        nav_label = QLabel("MENU PRINCIPAL")
        nav_label.setObjectName("sidebarSection")
        self._nav_label = nav_label
        side_layout.addWidget(nav_label)

        for label, icon_name, module in NAV_ITEMS:
            button = QPushButton(label)
            button.setIcon(qta.icon(icon_name, color="#C9D7EE", color_on="#FFFFFF", color_active="#FFFFFF", color_on_active="#FFFFFF"))
            button.setIconSize(QSize(17, 17))
            button.setObjectName("navButton")
            button.setToolTip(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.setMinimumHeight(38)
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
        topbar.setFixedHeight(64)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(20, 8, 24, 8)
        topbar_layout.setSpacing(12)

        menu_button = QPushButton()
        menu_button.setIcon(qta.icon("fa5s.bars", color="#102957"))
        menu_button.setIconSize(QSize(17, 17))
        menu_button.setObjectName("topbarIconButton")
        menu_button.setFixedSize(38, 38)
        menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_button.setCheckable(True)
        menu_button.setToolTip("Recolher ou expandir menu lateral")
        menu_button.setAccessibleName("Recolher ou expandir menu lateral")
        self._menu_button = menu_button
        menu_button.clicked.connect(self._toggle_sidebar)
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
        notifications.setCursor(Qt.CursorShape.PointingHandCursor)
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
        profile_menu.setFixedSize(30, 36)
        profile_menu.setCursor(Qt.CursorShape.PointingHandCursor)
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
        scroll_host.setObjectName("scrollHost")
        scroll_layout = QVBoxLayout(scroll_host)
        scroll_layout.setContentsMargins(24, 22, 24, 16)
        scroll_layout.addWidget(self._scroll)
        workspace_layout.addWidget(scroll_host, 1)

        side_footer = QLabel("AMT SISTEMAS  •  DESKTOP")
        side_footer.setObjectName("sidebarFooter")
        self._sidebar_footer = side_footer
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

    def _toggle_sidebar(self) -> None:
        """Alterna entre a navegação completa e a barra compacta somente com ícones."""
        self._sidebar_collapsed = not self._sidebar_collapsed
        collapsed = self._sidebar_collapsed
        self._menu_button.setChecked(collapsed)

        self._sidebar.setFixedWidth(76 if collapsed else 230)
        self._sidebar_layout.setContentsMargins(
            8 if collapsed else 18,
            16 if collapsed else 22,
            8 if collapsed else 18,
            14 if collapsed else 18,
        )
        self._sidebar_layout.setSpacing(4)

        for widget in (
            self._sidebar_logo,
            self._brand_subtitle,
            self._nav_label,
            self._sidebar_footer,
        ):
            widget.setVisible(not collapsed)

        for label, button in self._nav_buttons.items():
            button.setText("" if collapsed else label)
            # O nome do módulo aparece ao passar o mouse somente no modo compacto.
            button.setToolTip(label if collapsed else "")
            button.setAccessibleName(label)
            button.setMinimumWidth(0)
            button.setMaximumWidth(60 if collapsed else 16777215)
            button.setStyleSheet(
                "text-align: center; padding: 10px 0;"
                if collapsed
                else ""
            )

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

        if module == "Produtos" or module in MODULE_WINDOWS:
            try:
                if module == "Produtos":
                    # The catalog keeps its in-memory preview data while the app is open.
                    if self._products_window is None:
                        self._products_window = ProductsPage(preview_mode=self._preview_mode, parent=self)
                    self._products_window.exec()
                else:
                    MODULE_WINDOWS[module](preview_mode=self._preview_mode, parent=self).exec()
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
