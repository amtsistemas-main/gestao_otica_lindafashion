"""Checks GitHub for a new version in the background and applies it now or when the app closes."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from config.version import APP_VERSION, UPDATE_REPO
from core import updater
from ui.components.background import run_in_background

logger = logging.getLogger(__name__)
CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000
FIRST_CHECK_MS = 8_000


class UpdateNotifier(QObject):
    """Only active in the installed (frozen) app; ``OTICA_DISABLE_UPDATES=1`` turns it off."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._busy = False
        self._pending: Path | None = None
        self._offered: str | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self.check)
        app.aboutToQuit.connect(self._install_on_exit)

    @staticmethod
    def enabled() -> bool:
        return getattr(sys, "frozen", False) and os.environ.get("OTICA_DISABLE_UPDATES") != "1"

    def start(self) -> None:
        if not self.enabled():
            return
        QTimer.singleShot(FIRST_CHECK_MS, self.check)
        self._timer.start()

    def check(self) -> None:
        if self._busy or self._pending is not None:
            return
        self._busy = True
        run_in_background(self, lambda: updater.check_and_download(UPDATE_REPO, APP_VERSION),
                          self._on_checked, self._on_error)

    def _on_error(self, message: str) -> None:
        self._busy = False
        logger.warning("Verificação de atualização falhou: %s", message)

    def _on_checked(self, result: object) -> None:
        self._busy = False
        if not result:
            logger.info("Nenhuma atualização disponível (versão %s)", APP_VERSION)
            return
        release, installer = result
        self._pending = installer
        logger.info("Atualização %s baixada", release.version)
        if self._offered != release.version:
            self._offered = release.version
            self._offer(release)

    def _offer(self, release: updater.Release) -> None:
        notes = release.notes[:600] + ("…" if len(release.notes) > 600 else "")
        box = QMessageBox(self._app.activeWindow())
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Atualização disponível")
        box.setText(f"A versão {release.version} do sistema está pronta para instalar (versão atual: {APP_VERSION}).")
        box.setInformativeText("Atualizar agora fecha e reabre o sistema em alguns segundos. "
                               "Se preferir, a atualização é instalada automaticamente quando o sistema for fechado.")
        if notes:
            box.setDetailedText(notes)
        now = box.addButton("Atualizar agora", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Ao fechar o sistema", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(now)
        box.exec()
        if box.clickedButton() is now:
            self._apply(relaunch=True)

    def _apply(self, relaunch: bool) -> None:
        installer, self._pending = self._pending, None
        if installer is None or not installer.is_file():
            return
        try:
            updater.launch_installer(installer, relaunch=relaunch)
        except OSError as exc:
            logger.error("Não foi possível iniciar a atualização: %s", exc)
            return
        if relaunch:
            self._app.quit()

    def _install_on_exit(self) -> None:
        if self._pending is not None:
            self._apply(relaunch=False)
