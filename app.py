"""Application entry point for Ótica Linda Fashion."""
from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
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


def main() -> int:
    preview_mode = "--preview" in sys.argv
    qt_args = [arg for arg in sys.argv if arg != "--preview"]

    settings = get_settings()
    configure_logging(settings.log_level)

    app = QApplication(qt_args)
    app.setApplicationName("Ótica Linda Fashion")
    app.setOrganizationName("AMT Sistemas")
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
