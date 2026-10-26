"""Application entry point for Ótica Linda Fashion."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config.settings import get_settings
from config.version import APP_VERSION
from ui.components.update_notifier import UpdateNotifier
from ui.styles.theme import apply_theme
from ui.components.window_header import install_window_headers
from ui.windows.login_window import LoginWindow
from ui.windows.main_window import MainWindow


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()] if sys.stderr else []
    # The installed app has no console: keep a rotating log for support (no secrets are logged).
    base = os.environ.get("LOCALAPPDATA")
    if base:
        try:
            folder = Path(base) / "OticaLindaFashion" / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            handlers.append(RotatingFileHandler(folder / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
        except OSError:
            pass
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
    )


APP_ICON = Path(__file__).resolve().parent / "assets" / "images" / "app_icon.ico"


def set_windows_app_id() -> None:
    """Own taskbar identity on Windows, so the brand icon is shown instead of Python's."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AMTSistemas.OticaLindaFashion.Gestao")
    except Exception:
        pass


def smoke_test(app: QApplication) -> int:
    """Opens the main windows off-screen and exits: validates a packaged build."""
    from PySide6.QtCore import Qt

    problems = []
    if not APP_ICON.is_file():
        problems.append("ícone ausente")
    if not get_settings().supabase_configured:
        problems.append("configuração do Supabase ausente")
    for factory in (LoginWindow, lambda: MainWindow(preview_mode=True)):
        window = factory()
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        app.processEvents()
        window.close()
    print(f"smoke-test {APP_VERSION}: " + ("OK" if not problems else "FALHA - " + ", ".join(problems)))
    return 0 if not problems else 1


def main() -> int:
    preview_mode = "--preview" in sys.argv
    smoke = "--smoke-test" in sys.argv
    qt_args = [arg for arg in sys.argv if arg not in ("--preview", "--smoke-test")]

    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("Ótica Linda Fashion %s iniciado", APP_VERSION)

    set_windows_app_id()
    app = QApplication(qt_args)
    app.setApplicationName("Ótica Linda Fashion")
    app.setOrganizationName("AMT Sistemas")
    app.setApplicationVersion(APP_VERSION)
    # Brand mark in the title bar of every window and in the taskbar.
    if APP_ICON.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON)))
    app.setStyle("Fusion")
    # Native dialog buttons (Cancelar, Sim/Não) in Portuguese.
    translator = QTranslator(app)
    if translator.load("qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    apply_theme(app)
    install_window_headers(app)

    if smoke:
        return smoke_test(app)
    updates = UpdateNotifier(app)
    updates.start()
    if preview_mode:
        window = MainWindow(preview_mode=True)
    else:
        window = LoginWindow()

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
