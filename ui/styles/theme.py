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
    app.setStyleSheet(THEME_QSS + DASHBOARD_EXTRA_QSS)


DASHBOARD_EXTRA_QSS = """
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

QLineEdit#dashboardSearch {
    background: #F4F7FC;
    color: #263957;
    border: 1px solid #E5EAF3;
    border-radius: 10px;
    padding: 10px 13px;
    selection-background-color: #315FE8;
    selection-color: #FFFFFF;
}
QLineEdit#dashboardSearch:focus {
    background: #FFFFFF;
    border: 1px solid #AFC2F4;
}
QWidget#dashboardPage, QWidget#transparentHost {
    background: transparent;
}
QFrame#appSidebar {
    background: #0E2857;
    border-right: 1px solid #183968;
}
QLabel#sidebarLogo {
    background: transparent;
    padding: 0px;
}
QLabel#sidebarEyebrow {
    background: transparent;
    color: #D3DFF3;
    font-size: 7pt;
    letter-spacing: 1px;
}
QLabel#sidebarFooter {
    background: transparent;
    color: #9EB5DD;
    padding: 8px 0px;
}
QPushButton#navButton {
    background: transparent;
    color: #E4ECFA;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 10px 9px;
    text-align: left;
    font-size: 9pt;
    font-weight: 500;
}
QPushButton#navButton:hover {
    background: #18396F;
    color: #FFFFFF;
}
QPushButton#navButton:checked {
    background: #1557D8;
    color: #FFFFFF;
    border: 1px solid #2868EA;
    font-weight: 700;
}
QFrame#welcomeBanner {
    background: #F1F6FD;
    border: 1px solid #DFE9F8;
    border-radius: 12px;
}
QLabel#bannerGreeting {
    background: transparent;
    color: #102957;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#bannerTitle {
    background: transparent;
    color: #102957;
    font-size: 20pt;
    font-weight: 800;
}
QLabel#bannerDescription {
    background: transparent;
    color: #526D99;
    font-size: 9pt;
}
QLabel#bannerSlogan {
    background: transparent;
    color: #1C396B;
    font-family: Georgia;
    font-size: 13pt;
}
QLabel#bannerAccent {
    background: transparent;
    color: #1764F5;
    font-size: 10pt;
}
QFrame#analyticsCard, QFrame#metricCard {
    background: #FFFFFF;
    border: 1px solid #E1EAF7;
    border-radius: 10px;
}
QLabel#cardTitle {
    background: transparent;
    color: #102957;
    font-size: 10pt;
    font-weight: 750;
}
QLabel#sectionTitle {
    background: transparent;
    color: #102957;
    font-size: 12pt;
    font-weight: 750;
}
QLabel#actionHint {
    background: transparent;
    color: #6880A6;
    font-size: 8pt;
}
QPushButton#quickTile {
    background: #FFFFFF;
    color: #102957;
    border: 1px solid #DCE7F7;
    border-radius: 10px;
    text-align: left;
}
QPushButton#quickTile:hover {
    background: #F7FAFF;
    border: 1px solid #AFC7F6;
}
QLabel#quickIcon {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    border-radius: 15px;
    qproperty-alignment: AlignCenter;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#quickTitle {
    background: transparent;
    color: #1D4FAD;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#quickDescription {
    background: transparent;
    color: #7186A8;
    font-size: 8pt;
}
QLabel#quickArrow {
    background: transparent;
    color: #1764F5;
    font-size: 16pt;
}
QLabel#metricIcon {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    qproperty-alignment: AlignCenter;
    font-size: 12pt;
}
QLabel#metricLabel {
    background: transparent;
    color: #42577B;
    font-size: 9pt;
}
QLabel#metricValue {
    background: transparent;
    color: #102957;
    font-size: 20pt;
    font-weight: 800;
}
QLabel#metricGrowth {
    background: transparent;
    color: #0F9F70;
    font-size: 8pt;
    font-weight: 700;
}
QLabel#muted {
    background: transparent;
    color: #7084A5;
    font-size: 8pt;
}
QComboBox#periodSelector {
    background: #FFFFFF;
    color: #38557F;
    border: 1px solid #DCE6F5;
    border-radius: 8px;
    padding: 5px 8px;
    min-width: 62px;
}
QLabel#legendDot {
    background: transparent;
    font-size: 10pt;
}
QLabel#legendLabel, QLabel#stockLabel {
    background: transparent;
    color: #40577D;
    font-size: 8pt;
}
QLabel#legendValue, QLabel#stockValue {
    background: transparent;
    color: #304B75;
    font-size: 8pt;
    font-weight: 700;
}
QLabel#productThumb {
    background: #F1F5FB;
    color: #355E9B;
    border-radius: 7px;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    qproperty-alignment: AlignCenter;
    font-size: 14pt;
}
QLabel#productName, QLabel#activityTitle {
    background: transparent;
    color: #27436E;
    font-size: 8pt;
    font-weight: 600;
}
QLabel#productCode, QLabel#activityDetail, QLabel#activityTime {
    background: transparent;
    color: #7B8EAD;
    font-size: 7pt;
}
QLabel#activityIcon {
    min-width: 31px;
    max-width: 31px;
    min-height: 31px;
    max-height: 31px;
    border-radius: 16px;
    qproperty-alignment: AlignCenter;
    font-size: 12pt;
}
QPushButton#textAction {
    background: transparent;
    color: #1764F5;
    border: none;
    padding: 2px;
    font-size: 8pt;
}
QPushButton#textAction:hover {
    color: #0E43B8;
    text-decoration: underline;
}
QLabel#agendaDate {
    background: transparent;
    color: #27436E;
    font-size: 8pt;
    font-weight: 700;
}
QLabel#agendaTime {
    background: transparent;
    color: #60799E;
    font-size: 7pt;
}
QLabel#agendaDot {
    background: transparent;
    color: #1764F5;
    font-size: 8pt;
}
QFrame#promoCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7294B8, stop:0.45 #1F477A, stop:1 #102957);
    border: 1px solid #294D7B;
    border-radius: 9px;
}
QLabel#promoTitle {
    background: transparent;
    color: #FFFFFF;
    font-size: 11pt;
    font-weight: 750;
}
QLabel#promoCaption {
    background: transparent;
    color: #D8E5F7;
    font-size: 7pt;
}
QLabel#statusDot {
    background: transparent;
    color: #0F9F70;
}
QLabel#footerBrand {
    background: transparent;
    color: #7184A1;
    font-size: 8pt;
    font-weight: 750;
}
QPushButton#topbarIconButton {
    background: transparent;
    color: #102957;
    border: none;
    border-radius: 9px;
    font-size: 16pt;
}
QPushButton#topbarIconButton:hover {
    background: #EDF3FC;
}
QLabel#accountAvatar {
    background: #E4ECFA;
    color: #102957;
    border: 1px solid #D6E2F5;
    border-radius: 20px;
    font-size: 17pt;
}
QLabel#profileName {
    background: transparent;
    color: #102957;
    font-size: 9pt;
    font-weight: 750;
}
QLabel#profileRole {
    background: transparent;
    color: #60799E;
    font-size: 8pt;
}
QScrollArea#mainScroll {
    background: transparent;
    border: none;
}
QStatusBar {
    background: #FFFFFF;
    color: #7A8CA8;
    border-top: 1px solid #E6EDF7;
}
/* Typography and spacing refinement */
QWidget {
    font-family: "Segoe UI";
    font-size: 9pt;
}
QFrame#topbar {
    min-height: 70px;
}
QLabel#bannerGreeting {
    font-size: 10pt;
    font-weight: 650;
}
QLabel#bannerTitle {
    font-size: 23pt;
    font-weight: 800;
    letter-spacing: -0.4px;
}
QLabel#bannerDescription {
    font-size: 9pt;
    line-height: 1.35;
}
QLabel#cardTitle {
    font-size: 10.5pt;
    font-weight: 750;
}
QLabel#sectionTitle {
    font-size: 12pt;
    font-weight: 750;
}
QLabel#metricLabel {
    font-size: 9pt;
    font-weight: 550;
}
QLabel#metricValue {
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: -0.4px;
}
QLabel#metricGrowth, QLabel#muted {
    font-size: 8pt;
}
QLabel#quickTitle {
    font-size: 10pt;
    font-weight: 700;
}
QLabel#quickDescription {
    font-size: 8.5pt;
}
QLabel#productName, QLabel#activityTitle {
    font-size: 8.5pt;
    font-weight: 650;
}
QLabel#productCode, QLabel#activityDetail, QLabel#activityTime {
    font-size: 7.5pt;
}
QLabel#legendLabel, QLabel#stockLabel, QLabel#legendValue, QLabel#stockValue {
    font-size: 8.5pt;
}
QLabel#agendaDate {
    font-size: 9pt;
}
QLabel#agendaTime {
    font-size: 8pt;
}
QPushButton#navButton {
    padding: 11px 13px;
    spacing: 12px;
    font-size: 9.5pt;
    font-weight: 600;
}
QPushButton#navButton:checked {
    font-weight: 750;
}
QLineEdit#dashboardSearch {
    font-size: 9pt;
    padding: 11px 14px;
}
QLabel#sidebarEyebrow {
    font-size: 7.5pt;
    letter-spacing: 1.2px;
}
QPushButton#topbarIconButton {
    padding: 7px;
}
QLabel#moduleIcon {
    background: #EEF4FF;
    border: 1px solid #E2EBFC;
    border-radius: 14px;
}
QLabel#moduleTitle {
    color: #172B4D;
    font-size: 10pt;
    font-weight: 750;
}
QLabel#moduleDescription {
    color: #71819A;
    font-size: 8.5pt;
}
QPushButton#moduleCard {
    background: #FFFFFF;
    border: 1px solid #E2EAF5;
    border-radius: 12px;
    padding: 12px;
}
QPushButton#moduleCard:hover {
    background: #F8FAFF;
    border-color: #B9CCF3;
}

/* Product catalog: refined SaaS surface and clear actions */
QDialog {
    background: #F5F8FD;
    color: #172B4D;
}
QLabel#pageTitle {
    color: #102957;
    font-size: 23pt;
    font-weight: 800;
}
QLabel#sectionTitle {
    color: #102957;
    font-size: 11pt;
    font-weight: 750;
}
QLabel#muted {
    color: #7184A1;
    font-size: 9pt;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    color: #172B4D;
    border: 1px solid #D9E3F1;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #315FE8;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #5B83F0;
}
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F7F9FD;
    border: 1px solid #E0E8F4;
    border-radius: 12px;
    gridline-color: #EDF1F7;
    selection-background-color: #E8F0FF;
    selection-color: #102957;
    padding: 4px;
}
QTableWidget::item {
    padding: 7px 6px;
    border-bottom: 1px solid #EDF1F7;
}
QTableWidget::item:selected {
    background: #E8F0FF;
    color: #102957;
}
QHeaderView::section {
    background: #EFF4FC;
    color: #42577B;
    border: none;
    border-bottom: 1px solid #DCE5F2;
    padding: 12px 8px;
    font-size: 9pt;
    font-weight: 750;
}
QLabel#productImagePreview {
    background: #FFFFFF;
    color: #7A8CA8;
    border: 1px dashed #C9D7EA;
    border-radius: 10px;
    font-size: 8pt;
}
QPushButton#secondaryQuickAction {
    background: #FFFFFF;
    color: #244BAA;
    border: 1px solid #DCE5F5;
    border-radius: 9px;
    padding: 10px 12px;
    font-weight: 700;
}
QPushButton#secondaryQuickAction:hover {
    background: #F0F5FF;
    border-color: #B9C9F2;
}
QPushButton#primaryButton {
    background: #245DE0;
    color: #FFFFFF;
    border: 1px solid #245DE0;
    border-radius: 9px;
    padding: 11px 15px;
    font-weight: 750;
}
QPushButton#primaryButton:hover {
    background: #194FC9;
}

"""
