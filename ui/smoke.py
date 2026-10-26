"""Opens every main screen off-screen in preview mode: used by --smoke-test and by the tests.

A screen that raises while building (a typo, a shadowed name, a missing import) fails the
check before an installer is published.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget


def _screens() -> list[tuple[str, Callable[[], QWidget]]]:
    from modules.customers.page import CustomerFormDialog
    from modules.finance.page import FinancialEntryDialog, ReportExportDialog
    from modules.products.page import ProductFormDialog
    from modules.sales.pos import PosDialog
    from modules.settings.service import StoreSettings
    from modules.settings.users import UserFormDialog
    from modules.suppliers.page import SupplierFormDialog
    from ui.windows.login_window import LoginWindow
    from ui.windows.main_window import MODULE_WINDOWS, MainWindow

    screens: list[tuple[str, Callable[[], QWidget]]] = [
        ("Login", LoginWindow),
        ("Janela principal", lambda: MainWindow(preview_mode=True)),
    ]
    screens += [(f"Módulo {name}", lambda cls=cls: cls(preview_mode=True)) for name, cls in MODULE_WINDOWS.items()]
    screens += [
        ("PDV", lambda: PosDialog(None, StoreSettings())),
        ("Cadastro de produto", ProductFormDialog),
        ("Cadastro de cliente", CustomerFormDialog),
        ("Cadastro de fornecedor", SupplierFormDialog),
        ("Lançamento financeiro", FinancialEntryDialog),
        ("Exportar relatório financeiro", lambda: ReportExportDialog("Este mês")),
        ("Usuário e acessos", lambda: UserFormDialog(True)),
    ]
    return screens


def check_screens(app: QApplication) -> list[str]:
    """Returns one problem line per screen that failed to open."""
    problems: list[str] = []
    for name, factory in _screens():
        try:
            window = factory()
            window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            window.show()
            app.processEvents()
            window.close()
            window.deleteLater()
        except Exception as exc:  # reported, not raised: every screen is checked
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
    app.processEvents()
    return problems
