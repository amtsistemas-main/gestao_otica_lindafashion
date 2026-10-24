"""Application entry point for Ótica Linda Fashion."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from config.settings import get_settings
from ui.styles.theme import apply_theme
from ui.windows.login_window import LoginWindow


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = QApplication(sys.argv)
    app.setApplicationName("Ótica Linda Fashion")
    app.setOrganizationName("AMT Sistemas")
    app.setStyle("Fusion")
    apply_theme(app)

    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
