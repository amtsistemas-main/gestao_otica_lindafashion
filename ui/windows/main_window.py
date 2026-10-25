"""Main application shell with a premium SaaS navigation layout."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QSize
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
    QStackedWidget,
    QStatusBar,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config.branding import APP_NAME, WINDOW_TITLE
from core.auth_service import AuthService
from core.organization import OrganizationContext, current_organization
from core.permissions import ROLE_LABELS
from core.session_manager import session_manager
from core.usernames import username_from_email
from modules.products.page import ProductsPage
from modules.inventory.page import InventoryPage
from modules.suppliers.page import SuppliersPage
from modules.finance.page import FinancePage
from modules.customers.page import CustomersPage
from modules.sales.hub import SalesHubPage
from modules.crm.page import CrmPage
from modules.analytics.page import AnalyticsPage
from modules.settings.page import SettingsDialog
from ui.pages.dashboard_page import DashboardPage
from ui.components.ai_results_panel import BusinessAnalysisPanel
from ui.components.module_host import embed_dialog, scroll_container
from ui.components.profile_menu import ProfileChip
from core.ai_analysis_service import AIAnalysisWorker

LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "logootica.png"

NAV_ITEMS = [
    ("Visão geral", "fa5s.home", None),
    ("Vendas / PDV", "fa5s.cash-register", "Vendas"),
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

# First screen of each module, shown inside the workspace (in place of the overview).
# Each receives preview_mode and parent; secondary screens keep opening as windows.
MODULE_WINDOWS = {
    "Vendas": SalesHubPage,
    "Produtos": ProductsPage,
    "Clientes": CustomersPage,
    "Relacionamento": CrmPage,
    "Estoque": InventoryPage,
    "Fornecedores": SuppliersPage,
    "Financeiro": FinancePage,
    "Indicadores": AnalyticsPage,
    "Configurações": SettingsDialog,
}


class _NavHoverIcons(QObject):
    """Qt keeps a button's icon in Normal mode on hover; swap to the white icon on the blue hover."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Enter:
            watched.setIcon(watched.property("_hover_icon"))
        elif event.type() == QEvent.Type.Leave:
            watched.setIcon(watched.property("_normal_icon"))
        return False


class MainWindow(QMainWindow):
    def __init__(self, preview_mode: bool = False) -> None:
        super().__init__()
        self._preview_mode = preview_mode
        self.setWindowTitle(f"{WINDOW_TITLE} — Pré-visualização" if preview_mode else WINDOW_TITLE)
        self.resize(1440, 920)
        self.setMinimumSize(1024, 600)
        self._auth_service = AuthService()
        self._module_containers: dict[str, QScrollArea] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._nav_hover = _NavHoverIcons(self)
        # Modules released to this login (multilogin); preview mode shows everything.
        self._access: OrganizationContext | None = None
        if not preview_mode:
            try:
                self._access = current_organization("O sistema")
            except Exception:
                self._access = None
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
        # The menu scrolls on short screens instead of pushing the window off-screen.
        sidebar_outer = QVBoxLayout(sidebar)
        sidebar_outer.setContentsMargins(0, 0, 0, 0)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setObjectName("sidebarScroll")
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_body = QWidget()
        sidebar_body.setObjectName("sidebarBody")
        sidebar_scroll.setWidget(sidebar_body)
        sidebar_outer.addWidget(sidebar_scroll)
        side_layout = QVBoxLayout(sidebar_body)
        self._sidebar_layout = side_layout
        side_layout.setContentsMargins(18, 18, 18, 14)
        side_layout.setSpacing(3)

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

        side_layout.addSpacing(12)
        nav_label = QLabel("MENU PRINCIPAL")
        nav_label.setObjectName("sidebarSection")
        self._nav_label = nav_label
        side_layout.addWidget(nav_label)

        for label, icon_name, module in NAV_ITEMS:
            button = QPushButton(label)
            # White like the text, also on the blue hover and on the selected item.
            normal_icon = qta.icon(icon_name, color="#FFFFFF", color_on="#FFFFFF", color_active="#FFFFFF", color_on_active="#FFFFFF")
            button.setProperty("_normal_icon", normal_icon)
            button.setProperty("_hover_icon", qta.icon(icon_name, color="#FFFFFF"))
            button.setIcon(normal_icon)
            button.installEventFilter(self._nav_hover)
            button.setIconSize(QSize(17, 17))
            button.setObjectName("navButton")
            button.setToolTip(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.setMinimumHeight(36)
            button.setChecked(module is None)
            button.clicked.connect(
                lambda checked=False, selected=module: self._navigate(selected)
            )
            self._nav_buttons[label] = button
            button.setVisible(self._can_open(module))
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

        if preview_mode:
            profile_name, profile_role = "Ana Silva", "Administrador"
        else:
            profile_name = username_from_email(session_manager.current.email) if session_manager.current else "Usuário"
            profile_role = ROLE_LABELS.get(self._access.role, "Conta conectada") if self._access else "Conta conectada"
        # Signed-in user: clicking opens Configurações / Sair.
        self._profile_chip = ProfileChip(profile_name, profile_role, can_open_settings=self._can_open("Configurações"))
        self._profile_chip.settings_requested.connect(lambda: self._open_module("Configurações"))
        self._profile_chip.logout_requested.connect(self._confirm_logout)
        topbar_layout.addWidget(self._profile_chip)

        workspace_layout.addWidget(topbar)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("mainScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._dashboard = DashboardPage(preview_mode=preview_mode)
        self._dashboard.setContentsMargins(0, 0, 0, 0)
        self._dashboard.module_requested.connect(self._open_module)
        self._dashboard.apply_module_access(self._can_open)
        self._scroll.setWidget(self._dashboard)
        scroll_host = QWidget()
        scroll_host.setObjectName("scrollHost")
        scroll_layout = QVBoxLayout(scroll_host)
        scroll_layout.setContentsMargins(24, 22, 24, 16)
        scroll_layout.addWidget(self._scroll)
        # Overview and module pages share the workspace; only one is visible at a time.
        self._stack = QStackedWidget()
        self._stack.setObjectName("workspaceStack")
        self._overview = scroll_host
        self._stack.addWidget(scroll_host)
        workspace_layout.addWidget(self._stack, 1)

        side_footer = QLabel(
            "Desenvolvido por<br>AMT Sistemas &amp; Soluções<br>"
            "<a href='https://www.amtsistemas.com.br' style='color:#8FB4FF; text-decoration:none;'>"
            "https://www.amtsistemas.com.br</a>"
        )
        side_footer.setObjectName("sidebarFooter")
        side_footer.setTextFormat(Qt.TextFormat.RichText)
        side_footer.setOpenExternalLinks(True)
        side_footer.setWordWrap(True)
        side_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_footer.setToolTip("Abrir o site da AMT Sistemas & Soluções")
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

    def _check_nav(self, module: str | None) -> None:
        for label, _abbreviation, target in NAV_ITEMS:
            self._nav_buttons[label].setChecked(target == module)

    def _navigate(self, module: str | None) -> None:
        if module is None:
            self._show_overview()
            return
        self._open_module(module)

    def _show_overview(self) -> None:
        self._check_nav(None)
        self._show_page(self._overview)
        self._scroll.verticalScrollBar().setValue(0)

    def _show_page(self, container: QWidget) -> None:
        previous = self._stack.currentWidget()
        self._stack.setCurrentWidget(container)
        # Pages are rebuilt on each visit (fresh data, like the old windows); the catalog
        # is kept because preview mode stores its products in memory.
        for module, page in list(self._module_containers.items()):
            if page is previous and page is not container and module != "Produtos":
                del self._module_containers[module]
                self._stack.removeWidget(page)
                page.deleteLater()

    def _can_open(self, module: str | None) -> bool:
        return self._access is None or self._access.can_access(module)

    def _open_module(self, module: str) -> None:
        tab = None
        if module == "Pedidos":
            # Pedidos is part of Vendas / PDV.
            module, tab = "Vendas", SalesHubPage.TAB_ORDERS
        if not self._can_open(module):
            QMessageBox.information(self, "Acesso não liberado",
                                    f"Seu usuário não tem acesso ao módulo {module}. Fale com o administrador da loja.")
            return
        if module != "Análises" and module not in MODULE_WINDOWS:
            QMessageBox.information(self, module, f"O módulo {module.lower()} será implementado na próxima etapa.")
            return
        try:
            container = self._module_container(module)
        except Exception as exc:
            QMessageBox.critical(self, f"Não foi possível abrir {module}", str(exc))
            self._show_overview()
            return
        page = container.widget()
        if tab is not None and isinstance(page, SalesHubPage):
            page.show_tab(tab)
        self._check_nav(module)
        self._show_page(container)

    def _module_container(self, module: str) -> QScrollArea:
        cached = self._module_containers.get(module)
        if cached is not None and (module == "Produtos" or cached is self._stack.currentWidget()):
            return cached
        if cached is not None:
            del self._module_containers[module]
            self._stack.removeWidget(cached)
            cached.deleteLater()
        if module == "Análises":
            page = self._business_analysis_page()
        else:
            page = MODULE_WINDOWS[module](preview_mode=self._preview_mode, parent=self._stack)
            if isinstance(page, QDialog):
                # Pages that close themselves (e.g. after saving settings) return to the overview.
                embed_dialog(page, on_finished=self._show_overview)
        container = scroll_container(page)
        self._stack.addWidget(container)
        self._module_containers[module] = container
        return container

    def _business_analysis_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("analysisPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        panel = BusinessAnalysisPanel(page)
        panel.generate_requested.connect(
            lambda request: self._analysis_generation_unavailable(panel, request)
        )
        panel.regenerate_requested.connect(
            lambda request: self._analysis_generation_unavailable(panel, request)
        )
        layout.addWidget(panel)
        return page

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

    def _confirm_logout(self) -> None:
        if self._preview_mode:
            if QMessageBox.question(self, "Sair", "Encerrar a pré-visualização?") == QMessageBox.StandardButton.Yes:
                self.close()
            return
        if QMessageBox.question(self, "Sair", "Deseja sair da sua conta?") == QMessageBox.StandardButton.Yes:
            self._logout()

    def _logout(self) -> None:
        self._auth_service.sign_out()
        self.close()
        from ui.windows.login_window import LoginWindow

        self._login_window = LoginWindow()
        self._login_window.show()
