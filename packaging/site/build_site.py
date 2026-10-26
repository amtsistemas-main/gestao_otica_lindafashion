"""Builds the hidden download page: python packaging/site/build_site.py <route>

The route (folder name) is the only thing keeping the page unlisted, so it is passed on the
command line and never committed: this repository is public. Output: dist/site/<route>/ and a
zip to upload and extract in the site's public_html.
"""
from __future__ import annotations

import base64
import io
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

HTACCESS = """# Página de download não listada: fora dos buscadores e sem listagem de pastas.
Options -Indexes
<IfModule mod_headers.c>
  Header set X-Robots-Tag "noindex, nofollow, noarchive"
  Header set Referrer-Policy "no-referrer"
</IfModule>
"""


def logo_data_uri(width: int = 520) -> str:
    image = Image.open(ROOT / "assets" / "images" / "logootica.png").convert("RGBA")
    image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z0-9-]{8,64}", sys.argv[1]):
        print("Uso: python packaging/site/build_site.py <rota> (letras minúsculas, números e hífen)")
        return 2
    route = sys.argv[1]
    repo = re.search(r'UPDATE_REPO = "([^"]+)"', (ROOT / "config" / "version.py").read_text(encoding="utf-8")).group(1)
    html = (HERE / "index.template.html").read_text(encoding="utf-8")
    html = (html.replace("{{LOGO}}", logo_data_uri())
                .replace("{{REPO}}", repo)
                .replace("{{DOWNLOAD_URL}}", f"https://github.com/{repo}/releases/latest/download/OticaLindaFashion-Setup.exe"))
    out = ROOT / "dist" / "site"
    shutil.rmtree(out, ignore_errors=True)
    folder = out / route
    folder.mkdir(parents=True)
    (folder / "index.html").write_text(html, encoding="utf-8")
    (folder / ".htaccess").write_text(HTACCESS, encoding="utf-8")
    archive = shutil.make_archive(str(out / route), "zip", root_dir=out, base_dir=route)
    print(f"Página: {folder / 'index.html'}")
    print(f"Pacote para upload: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
