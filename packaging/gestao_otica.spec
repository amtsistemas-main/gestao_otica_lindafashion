# PyInstaller spec — build with packaging\build.ps1 (it generates build\app.env first).
# -*- mode: python ; coding: utf-8 -*-
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                  VarFileInfo, VarStruct, VSVersionInfo)

ROOT = Path(SPECPATH).parent
VERSION = re.search(r'APP_VERSION = "([^"]+)"', (ROOT / "config" / "version.py").read_text(encoding="utf-8")).group(1)
NUMBERS = tuple(int(part) for part in (VERSION.split(".") + ["0", "0", "0"])[:4])
APP_ENV = ROOT / "build" / "app.env"
if not APP_ENV.is_file():
    raise SystemExit("build/app.env ausente: execute packaging\\build.ps1")

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS),
    kids=[
        StringFileInfo([StringTable("041604B0", [
            StringStruct("CompanyName", "AMT Sistemas & Soluções"),
            StringStruct("FileDescription", "Ótica Linda Fashion — Gestão"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "OticaLindaFashion"),
            StringStruct("LegalCopyright", "© AMT Sistemas & Soluções"),
            StringStruct("OriginalFilename", "OticaLindaFashion.exe"),
            StringStruct("ProductName", "Ótica Linda Fashion"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
    ],
)

# Qt modules the app never uses — keeps the installer small.
QT_EXCLUDES = [
    "PySide6." + name for name in (
        "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender", "QtBluetooth",
        "QtCharts", "QtDataVisualization", "QtGraphs", "QtLocation", "QtMultimedia", "QtMultimediaWidgets",
        "QtNfc", "QtPositioning", "QtQuick", "QtQuick3D", "QtQuickControls2", "QtQuickWidgets", "QtQml",
        "QtRemoteObjects", "QtScxml", "QtSensors", "QtSerialBus", "QtSerialPort", "QtSpatialAudio", "QtSql",
        "QtTest", "QtTextToSpeech", "QtWebChannel", "QtWebEngineCore", "QtWebEngineQuick",
        "QtWebEngineWidgets", "QtWebSockets", "QtWebView", "QtDesigner", "QtHelp", "QtUiTools",
    )
]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "assets"), "assets"), (str(APP_ENV), ".")],
    # reportlab loads every barcode symbology by name at import time.
    hiddenimports=["PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPrintSupport", "PySide6.QtSvg"]
    + collect_submodules("reportlab.graphics.barcode"),
    excludes=QT_EXCLUDES + ["tkinter", "pytest", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OticaLindaFashion",
    icon=str(ROOT / "assets" / "images" / "app_icon.ico"),
    version=version_info,
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="OticaLindaFashion", upx=False)
