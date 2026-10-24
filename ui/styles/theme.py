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
QFrame#quickActionsCard {
    background: #FFFFFF;
    border: 1px solid #E2E8F2;
    border-radius: 15px;
}
QPushButton#primaryQuickAction {
    background: #315FE8;
    color: #FFFFFF;
    border: 1px solid #315FE8;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 800;
}
QPushButton#primaryQuickAction:hover {
    background: #244FCB;
    border-color: #244FCB;
}
QPushButton#secondaryQuickAction {
    background: #F4F7FD;
    color: #244BAA;
    border: 1px solid #DCE5F5;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 750;
}
QPushButton#secondaryQuickAction:hover {
    background: #EAF0FF;
    border-color: #B9C9F2;
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
/* Login: palette aligned to the brand with a clear blue primary action */
QWidget#loginBackground {
    background: #F2F5FB;
}
QFrame#loginBrandPanel {
    background: #172F59;
    border: 1px solid #244779;
    border-radius: 22px;
}
QLabel#loginLogo, QLabel#loginLogoFallback {
    background: transparent;
    color: #FFFFFF;
}
QLabel#loginLogoFallback {
    font-size: 21pt;
    font-weight: 800;
}
QLabel#loginEyebrow {
    background: transparent;
    color: #B9D0FF;
    font-size: 8pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#loginBrandTitle {
    background: transparent;
    color: #FFFFFF;
    font-size: 27pt;
    font-weight: 800;
}
QLabel#loginBrandDescription {
    background: transparent;
    color: #D9E5FA;
    font-size: 11pt;
}
QFrame#loginFeature {
    background: #213F70;
    border: 1px solid #34588C;
    border-radius: 13px;
}
QLabel#loginFeatureTitle {
    background: transparent;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 11pt;
}
QLabel#loginFeatureText {
    background: transparent;
    color: #D9E5FA;
    font-size: 9pt;
}
QLabel#loginBrandFooter {
    background: transparent;
    color: #B9C9E3;
    font-size: 8pt;
    font-weight: 700;
}
QFrame#loginFormHost {
    background: transparent;
    border: none;
}
QFrame#loginCard {
    background: #FFFFFF;
    border: 1px solid #E0E7F2;
    border-radius: 20px;
}
QLabel#loginFormEyebrow {
    background: transparent;
    color: #315FE8;
    font-size: 8pt;
    font-weight: 800;
}
QLabel#loginFormTitle {
    background: transparent;
    color: #152342;
    font-size: 23pt;
    font-weight: 800;
}
QLabel#fieldLabel {
    background: transparent;
    color: #34435D;
    font-weight: 700;
}
QLineEdit#loginInput {
    background: #FBFCFF;
    color: #19243A;
    border: 1px solid #D8E1EF;
    border-radius: 10px;
    padding: 10px 13px;
    selection-background-color: #315FE8;
    selection-color: #FFFFFF;
}
QLineEdit#loginInput:focus {
    background: #FFFFFF;
    border: 1px solid #315FE8;
}
QLabel#loginStatus {
    background: transparent;
    color: #C2414B;
    font-size: 9pt;
}
QPushButton#primaryButton {
    background: #315FE8;
    color: #FFFFFF;
    border: 1px solid #315FE8;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 10pt;
    font-weight: 800;
}
QPushButton#primaryButton:hover {
    background: #244FCB;
    border-color: #244FCB;
}
QPushButton#primaryButton:pressed {
    background: #1D43AD;
}
QPushButton#primaryButton:disabled {
    background: #91A9EE;
    border-color: #91A9EE;
    color: #FFFFFF;
}
QLabel#loginSecurityNote {
    background: transparent;
    color: #7B879C;
    font-size: 8pt;
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


/* Dashboard visual refresh: navy navigation, white surfaces and airy analytics. */
QFrame#appSidebar {
    background: #102957;
    border-right: 1px solid #193967;
}
QLabel#sidebarBrand {
    color: #FFFFFF;
    font-size: 10pt;
}
QLabel#sidebarEyebrow, QLabel#sidebarSection {
    color: #9EB5DD;
}
QLabel#sidebarFooter {
    color: #9EB5DD;
}
QLabel#logoFallback {
    background: #244A83;
    color: #FFFFFF;
}
QPushButton#navButton {
    background: transparent;
    color: #D5E1F5;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 11px 9px;
    text-align: left;
    font-weight: 600;
}
QPushButton#navButton:hover {
    background: #1A3A70;
    color: #FFFFFF;
}
QPushButton#navButton:checked {
    background: #245DE0;
    color: #FFFFFF;
    border: 1px solid #3D72EE;
    font-weight: 800;
}
QLabel#bannerEyebrow {
    background: transparent;
    color: #BDD1FF;
    font-size: 8pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#bannerTitle {
    background: transparent;
    color: #FFFFFF;
    font-size: 20pt;
    font-weight: 800;
}
QLabel#bannerDescription {
    background: transparent;
    color: #DDE7FA;
    font-size: 10pt;
}
QFrame#welcomeBanner {
    background: #193765;
    border: 1px solid #274A7C;
    border-radius: 16px;
}
QFrame#analyticsCard {
    background: #FFFFFF;
    border: 1px solid #E4EAF4;
    border-radius: 13px;
}
QLabel#chartTitle {
    background: transparent;
    color: #172849;
    font-size: 11pt;
    font-weight: 800;
}
QLabel#chartCategoryLabel {
    background: transparent;
    color: #40516D;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#chartValue {
    background: transparent;
    color: #25395E;
    font-size: 9pt;
    font-weight: 750;
}
QLabel#emptyState {
    background: #F8FAFE;
    color: #8491A6;
    border: 1px dashed #DCE4F0;
    border-radius: 9px;
    padding: 12px;
}
QFrame#dashboardFooter {
    background: #FFFFFF;
    border: 1px solid #E4EAF4;
    border-radius: 10px;
}
QFrame#quickActionsCard {
    background: #FFFFFF;
    border: 1px solid #E4EAF4;
    border-radius: 13px;
}
QPushButton#primaryQuickAction {
    background: #315FE8;
    color: #FFFFFF;
    border: 1px solid #315FE8;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 800;
}
QPushButton#primaryQuickAction:hover {
    background: #244FCB;
}
QPushButton#secondaryQuickAction {
    background: #FFFFFF;
    color: #244BAA;
    border: 1px solid #DCE5F5;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 750;
}
QPushButton#secondaryQuickAction:hover {
    background: #F1F5FF;
    border-color: #B9C9F2;
}
QLabel#metricValue {
    font-size: 21pt;
}
QScrollArea#mainScroll {
    background: transparent;
    border: none;
}
