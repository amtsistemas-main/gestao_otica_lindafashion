"""Main application shell."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QStatusBar, QVBoxLayout, QWidget

from config.branding import APP_NAME, WINDOW_TITLE
from core.auth_service import AuthService
from core.session_manager import session_manager
from ui.components.module_card import ModuleCard
from ui.pages.dashboard_page import DashboardPage

MODULES = [
    ("Produtos", "Cadastro, preços e códigos de barras"),
    ("Estoque", "Entradas, saídas e posição de estoque"),
    ("Fornecedores", "Cadastro e relacionamento comercial"),
    ("Financeiro", "Receitas, despesas e fluxo de caixa"),
    ("Relatórios", "Indicadores e consultas gerenciais"),
    ("Configurações", "Conexão, sessão e preferências"),
]

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1180, 780)
        self.setMinimumSize(900, 620)
        self._auth_service = AuthService()
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(22)
        header = QHBoxLayout()
        identity = QVBoxLayout()
        brand = QLabel(APP_NAME)
        brand.setStyleSheet("font-size:19pt; font-weight:800; color:#172c52;")
        subtitle = QLabel("Painel de gestão")
        subtitle.setObjectName("muted")
        identity.addWidget(brand)
        identity.addWidget(subtitle)
        header.addLayout(identity)
        header.addStretch()
        user_email = session_manager.current.email if session_manager.current else ""
        account_label = QLabel(user_email)
        account_label.setObjectName("muted")
        header.addWidget(account_label)
        logout_button = QPushButton("Sair")
        logout_button.clicked.connect(self._logout)
        header.addWidget(logout_button)
        root.addLayout(header)
        root.addWidget(DashboardPage())
        section = QLabel("Módulos")
        section.setStyleSheet("font-size:15pt; font-weight:700; color:#172c52;")
        root.addWidget(section)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for index, (name, description) in enumerate(MODULES):
            card = ModuleCard(name, description)
            card.clicked.connect(lambda checked=False, module=name: self._open_module(module))
            grid.addWidget(card, index // 3, index % 3)
        root.addWidget(grid_host)
        root.addStretch()
        self.setCentralWidget(central)
        status = QStatusBar()
        status.showMessage("Interface inicial • Módulos serão implementados por etapa")
        self.setStatusBar(status)

    def _open_module(self, module: str) -> None:
        QMessageBox.information(self, module, f"O módulo {module.lower()} será implementado na próxima etapa.")

    def _logout(self) -> None:
        self._auth_service.sign_out()
        self.close()
        from ui.windows.login_window import LoginWindow
        self._login_window = LoginWindow()
        self._login_window.show()
