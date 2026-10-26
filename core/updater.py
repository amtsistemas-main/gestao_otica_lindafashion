"""Automatic updates from GitHub Releases (public releases repository, no token in the client).

Each release carries the Inno Setup installer and a ``.sha256`` file; the installer is only
run after its hash matches. Updates run silently, per user, without administrator rights.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

INSTALLER_RE = re.compile(r"^OticaLindaFashion-Setup-[\d.]+\.exe$")
TIMEOUT = 20


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Release:
    version: str
    installer_name: str
    installer_url: str
    sha256_url: str
    notes: str = ""


def parse_version(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value or "")
    return tuple(int(number) for number in (numbers + ["0", "0", "0"])[:3])


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def updates_folder() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "OticaLindaFashion" / "updates"


def _request(url: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "OticaLindaFashion-Updater"})


def release_from_payload(payload: dict) -> Release | None:
    """Picks the installer and its hash from a GitHub release; drafts and prereleases are ignored."""
    if payload.get("draft") or payload.get("prerelease"):
        return None
    assets = {asset.get("name", ""): asset.get("browser_download_url", "") for asset in payload.get("assets") or []}
    installer = next((name for name in assets if INSTALLER_RE.match(name)), None)
    if installer is None or f"{installer}.sha256" not in assets:
        return None
    return Release(
        version=str(payload.get("tag_name", "")).lstrip("vV"),
        installer_name=installer,
        installer_url=assets[installer],
        sha256_url=assets[f"{installer}.sha256"],
        notes=(payload.get("body") or "").strip(),
    )


def fetch_latest(repo: str) -> Release | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with urllib.request.urlopen(_request(url, "application/vnd.github+json"), timeout=TIMEOUT) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # no release published yet
            return None
        raise UpdateError(f"GitHub respondeu {exc.code}") from exc
    return release_from_payload(payload)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(release: Release, folder: Path | None = None) -> Path:
    """Downloads the installer (reusing a verified earlier download) and checks its SHA-256."""
    folder = folder or updates_folder()
    folder.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_request(release.sha256_url, "application/octet-stream"), timeout=TIMEOUT) as response:
        expected = response.read().decode("utf-8", "replace").split()[0].strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise UpdateError("Arquivo de verificação da atualização inválido.")
    target = folder / release.installer_name
    for old in folder.glob("OticaLindaFashion-Setup-*"):
        if old.name != target.name:
            old.unlink(missing_ok=True)
    if target.is_file() and _sha256(target) == expected:
        return target
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(_request(release.installer_url, "application/octet-stream"), timeout=TIMEOUT) as response, \
            partial.open("wb") as handle:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            handle.write(chunk)
    if _sha256(partial) != expected:
        partial.unlink(missing_ok=True)
        raise UpdateError("A atualização baixada está corrompida e foi descartada.")
    partial.replace(target)
    return target


def check_and_download(repo: str, current: str) -> tuple[Release, Path] | None:
    release = fetch_latest(repo)
    if release is None or not is_newer(release.version, current):
        return None
    return release, download(release)


def launch_installer(installer: Path, relaunch: bool) -> None:
    """Starts the silent installer detached; the app must quit right after so its files can be replaced."""
    args = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            f"/RELAUNCH={1 if relaunch else 0}"]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags, close_fds=True)
    logger.info("Atualização iniciada: %s", installer.name)
