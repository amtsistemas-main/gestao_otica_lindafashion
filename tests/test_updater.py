import hashlib

import pytest

from core import updater


def _payload(**overrides):
    payload = {
        "tag_name": "v1.2.0",
        "draft": False,
        "prerelease": False,
        "body": "Novidades",
        "assets": [
            {"name": "OticaLindaFashion-Setup.exe", "browser_download_url": "https://x/fixed.exe"},
            {"name": "OticaLindaFashion-Setup-1.2.0.exe", "browser_download_url": "https://x/setup.exe"},
            {"name": "OticaLindaFashion-Setup-1.2.0.exe.sha256", "browser_download_url": "https://x/setup.sha256"},
        ],
    }
    payload.update(overrides)
    return payload


def test_versions_compare_numerically():
    assert updater.parse_version("v1.10.0") == (1, 10, 0)
    assert updater.parse_version("2") == (2, 0, 0)
    assert updater.is_newer("1.10.0", "1.9.3")
    assert not updater.is_newer("v1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.9", "1.0.0")


def test_release_requires_installer_and_hash():
    release = updater.release_from_payload(_payload())
    assert release.version == "1.2.0"
    assert release.installer_url == "https://x/setup.exe"
    assert release.sha256_url == "https://x/setup.sha256"
    assert updater.release_from_payload(_payload(assets=_payload()["assets"][:2])) is None
    assert updater.release_from_payload(_payload(draft=True)) is None
    assert updater.release_from_payload(_payload(prerelease=True)) is None


def _release_files(tmp_path, content: bytes, digest: str | None = None):
    source = tmp_path / "source"
    source.mkdir()
    installer = source / "OticaLindaFashion-Setup-1.2.0.exe"
    installer.write_bytes(content)
    hash_file = source / "setup.sha256"
    hash_file.write_text(f"{digest or hashlib.sha256(content).hexdigest()}  {installer.name}\n")
    return updater.Release("1.2.0", installer.name, installer.as_uri(), hash_file.as_uri())


def test_download_verifies_hash_and_removes_old_installers(tmp_path):
    folder = tmp_path / "updates"
    folder.mkdir()
    (folder / "OticaLindaFashion-Setup-1.1.0.exe").write_bytes(b"old")
    target = updater.download(_release_files(tmp_path, b"installer-bytes"), folder)
    assert target.read_bytes() == b"installer-bytes"
    assert [path.name for path in folder.iterdir()] == ["OticaLindaFashion-Setup-1.2.0.exe"]


def test_download_rejects_corrupted_installer(tmp_path):
    folder = tmp_path / "updates"
    release = _release_files(tmp_path, b"tampered", digest=hashlib.sha256(b"original").hexdigest())
    with pytest.raises(updater.UpdateError):
        updater.download(release, folder)
    assert not any(folder.iterdir())
