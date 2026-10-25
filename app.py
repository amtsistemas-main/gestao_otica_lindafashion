"""Application entry point for Ótica Linda Fashion."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config.settings import get_settings
from ui.styles.theme import apply_theme
from ui.components.window_header import install_window_headers
from ui.windows.login_window import LoginWindow
from ui.windows.main_window import MainWindow


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
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


def main() -> int:
    preview_mode = "--preview" in sys.argv
    qt_args = [arg for arg in sys.argv if arg != "--preview"]

    settings = get_settings()
    configure_logging(settings.log_level)

    set_windows_app_id()
    app = QApplication(qt_args)
    app.setApplicationName("Ótica Linda Fashion")
    app.setOrganizationName("AMT Sistemas")
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

    if preview_mode:
        window = MainWindow(preview_mode=True)
    else:
        window = LoginWindow()

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
