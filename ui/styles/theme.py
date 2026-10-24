"""Premium light theme shared by the desktop application."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


THEME_QSS = """
QWidget {
    background: #F5F7FB;
    color: #19243A;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #F5F7FB;
}
QFrame#appSidebar {
    background: #FFFFFF;
    border-right: 1px solid #E6EAF2;
}
QFrame#workspace, QFrame#topbar {
    background: #F5F7FB;
    border: none;
}
QFrame#topbar {
    background: #FFFFFF;
    border-bottom: 1px solid #E7EBF3;
}
QLabel#sidebarBrand {
    background: transparent;
    color: #152342;
    font-size: 11pt;
    font-weight: 800;
}
QLabel#sidebarEyebrow, QLabel#sidebarSection, QLabel#eyebrow {
    background: transparent;
    color: #8290A7;
    font-size: 8pt;
    font-weight: 800;
}
QLabel#sidebarSection {
    padding: 5px 8px;
}
QLabel#sidebarFooter {
    background: transparent;
    color: #97A2B5;
    font-size: 8pt;
    font-weight: 700;
    padding: 8px 2px;
}
QLabel#logoFallback {
    background: #EAF0FF;
    color: #2457D6;
    border-radius: 12px;
    font-size: 16pt;
    font-weight: 800;
}
QLabel#topbarTitle {
    background: transparent;
    color: #152342;
    font-size: 12pt;
    font-weight: 750;
}
QLabel#accountLabel {
    background: #FFFFFF;
    color: #526079;
    border: 1px solid #E0E6F0;
    border-radius: 9px;
    padding: 9px 12px;
}
QLabel#previewBadge {
    background: #FFF4D9;
    color: #825A09;
    border: 1px solid #F1D99A;
    border-radius: 9px;
    padding: 9px 12px;
    font-size: 8pt;
    font-weight: 800;
}
QLabel#dashboardTitle {
    background: transparent;
    color: #14213D;
    font-size: 25pt;
    font-weight: 800;
}
QLabel#sectionTitle {
    background: transparent;
    color: #19243A;
    font-size: 13pt;
    font-weight: 750;
}
QLabel#muted {
    background: transparent;
    color: #718099;
}
QLabel#heroEyebrow {
    background: transparent;
    color: #D5E1FF;
    font-size: 8pt;
    font-weight: 800;
}
QLabel#heroTitle {
    background: transparent;
    color: #FFFFFF;
    font-size: 23pt;
    font-weight: 800;
}
QLabel#heroDescription {
    background: transparent;
    color: #DCE5FA;
    font-size: 10pt;
}
QFrame#welcomeBanner {
    background: #182C50;
    border: 1px solid #253D68;
    border-radius: 18px;
}
QPushButton#heroButton {
    background: #FFFFFF;
    color: #1B3260;
    border: 1px solid #FFFFFF;
    border-radius: 10px;
    padding: 12px 18px;
    font-weight: 800;
}
QPushButton#heroButton:hover {
    background: #EAF0FF;
    border-color: #EAF0FF;
}
QFrame#metricCard {
    background: #FFFFFF;
    border: 1px solid #E5EAF2;
    border-radius: 14px;
}
QLabel#metricLabel {
    background: transparent;
    color: #687791;
    font-size: 9pt;
    font-weight: 650;
}
QLabel#metricValue {
    background: transparent;
    color: #152342;
    font-size: 23pt;
    font-weight: 800;
}
QPushButton#navButton {
    background: transparent;
    color: #65738A;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 11px 10px;
    text-align: left;
    font-weight: 650;
}
QPushButton#navButton:hover {
    background: #F4F7FC;
    color: #244BAA;
}
QPushButton#navButton:checked {
    background: #EAF0FF;
    color: #2457D6;
    border: 1px solid #DCE6FF;
    font-weight: 800;
}
QPushButton#logoutButton {
    background: #FFFFFF;
    color: #526079;
    border: 1px solid #E0E6F0;
    border-radius: 9px;
    padding: 9px 14px;
}
QPushButton#logoutButton:hover {
    background: #F4F7FC;
}
QPushButton#moduleCard {
    background: #FFFFFF;
    text-align: left;
    padding: 14px;
    min-height: 110px;
    border: 1px solid #E3E9F3;
    border-radius: 14px;
}
QPushButton#moduleCard:hover {
    border: 1px solid #A9BDF5;
    background: #FCFDFF;
}
QLabel#moduleIcon {
    background: #EDF2FF;
    color: #315FE8;
    border-radius: 9px;
    font-size: 9pt;
    font-weight: 800;
    padding: 7px;
}
QLabel#moduleTitle {
    background: transparent;
    color: #19243A;
    font-size: 11pt;
    font-weight: 750;
}
QLabel#moduleDescription {
    background: transparent;
    color: #718099;
    font-size: 9pt;
}
QFrame#dashboardFooter {
    background: #FFFFFF;
    border: 1px solid #E5EAF2;
    border-radius: 11px;
}
QLabel#footerBrand {
    background: transparent;
    color: #64728A;
    font-weight: 800;
}
QStatusBar {
    background: #FFFFFF;
    color: #718099;
    border-top: 1px solid #E5EAF2;
}
QStatusBar::item {
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #CBD4E4;
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #AAB7CD;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFD;
    color: #19243A;
    gridline-color: #E7EBF3;
    border: 1px solid #E3E9F3;
    border-radius: 10px;
    selection-background-color: #EAF0FF;
    selection-color: #19243A;
}
QHeaderView::section {
    background: #F4F7FC;
    color: #5D6B83;
    border: none;
    border-bottom: 1px solid #E1E7F0;
    padding: 10px 8px;
    font-weight: 750;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(THEME_QSS)
