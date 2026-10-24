"""Clean light theme shared by all application windows."""
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


THEME_QSS = """
QWidget {
    background: #f4f6fa;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #f4f6fa;
}
QFrame#panel, QFrame#loginCard {
    background: #ffffff;
    border: 1px solid #e2e7f0;
    border-radius: 14px;
}
QLabel#brandTitle {
    color: #152342;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#pageTitle {
    color: #152342;
    font-size: 19pt;
    font-weight: 700;
}
QLabel#muted {
    color: #68758b;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd7e5;
    border-radius: 8px;
    padding: 9px 10px;
    selection-background-color: #2457d6;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 26px;
    background: #2457d6;
    border: none;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    border-top-right-radius: 7px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    border-bottom-right-radius: 7px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #1b46b7;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(@SPIN_UP@);
    width: 9px;
    height: 9px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(@SPIN_DOWN@);
    width: 9px;
    height: 9px;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #2457d6;
}
QPushButton {
    background: #ffffff;
    color: #24314a;
    border: 1px solid #d5ddeb;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f0f4fc;
    border-color: #b6c6e5;
}
QPushButton:disabled {
    color: #929bad;
    background: #edf0f5;
}
QPushButton#primaryButton {
    background: #2457d6;
    color: #ffffff;
    border: 1px solid #2457d6;
}
QPushButton#primaryButton:hover {
    background: #1b46b7;
}
QPushButton#moduleCard {
    background: #ffffff;
    text-align: left;
    padding: 18px;
    min-height: 104px;
    border: 1px solid #e2e7f0;
    border-radius: 14px;
}
QPushButton#moduleCard:hover {
    border: 1px solid #8da9ed;
    background: #fafdff;
}
QStatusBar {
    background: #ffffff;
    color: #68758b;
    border-top: 1px solid #e2e7f0;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setFont(QFont("Segoe UI", 10))
    assets = Path(__file__).resolve().parents[2] / "assets" / "images"
    stylesheet = THEME_QSS.replace("@SPIN_UP@", str(assets / "spin-up-white.svg"))
    stylesheet = stylesheet.replace("@SPIN_DOWN@", str(assets / "spin-down-white.svg"))
    app.setStyleSheet(stylesheet)
