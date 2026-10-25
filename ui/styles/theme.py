"""Premium light design system shared by the whole desktop application.

Every window inherits this single stylesheet. Colours are defined once as tokens
(``PALETTE``) and injected into the QSS template, so module dialogs should not
declare their own colours; they only assign object names (``primaryButton``,
``windowTitleBar``, ``metricTile``...) that this theme styles.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "images"

PALETTE = {
    # Brand
    "navy": "#102957",
    "navy_2": "#1B3A72",
    "navy_line": "#203D68",
    "navy_hover": "#1A3A70",
    "primary": "#2165F5",
    "primary_hover": "#1749C2",
    "primary_pressed": "#103A9F",
    "primary_soft": "#EAF1FF",
    "primary_soft_2": "#DCE8FF",
    "primary_disabled": "#A8BDEB",
    # Surfaces
    "canvas": "#F4F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFD",
    "surface_muted": "#F1F4F9",
    "border": "#E2E8F0",
    "border_strong": "#CFD9E8",
    "border_hover": "#A9BCD9",
    # Text
    "text": "#1E2F4D",
    "text_strong": "#0F1B3D",
    "text_muted": "#64748B",
    "text_soft": "#8A97AB",
    "on_navy": "#FFFFFF",
    "on_navy_muted": "#C9D7EE",
    # Semantic
    "success": "#12A16B",
    "success_soft": "#E8F7F0",
    "warning": "#B7791F",
    "warning_soft": "#FFF6E0",
    "danger": "#D64545",
    "danger_soft": "#FDECEC",
}

FONT_FAMILY = "Arial"


THEME_QSS = """
/* =====================================================================
   Base
   ===================================================================== */
QWidget {
    color: @text@;
    font-family: Arial, "Liberation Sans", Helvetica, sans-serif;
    font-size: 9.5pt;
}
QMainWindow, QDialog, QWidget#appShell {
    background: @canvas@;
}
QLabel {
    background: transparent;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget#qt_scrollarea_viewport {
    background: transparent;
}
QToolTip {
    background: @navy@;
    color: @on_navy@;
    border: 1px solid @navy_line@;
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 9pt;
}

/* =====================================================================
   Typography helpers
   ===================================================================== */
QLabel#muted, QLabel#sectionDescription, QLabel#helpText {
    color: @text_muted@;
    font-size: 9pt;
}
QLabel#sectionTitle, QLabel#sectionLabel {
    color: @navy@;
    font-size: 12pt;
    font-weight: 700;
}
QLabel#summaryStrong {
    color: @text_strong@;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#fieldLabel, QLabel#productFieldLabel, QLabel#filterLabel {
    color: #334766;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#formSectionTitle {
    color: @navy@;
    background: @primary_soft@;
    border: 1px solid #D6E3FB;
    border-left: 4px solid @primary@;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#emptyState {
    background: @surface_alt@;
    color: @text_soft@;
    border: 1px dashed @border_strong@;
    border-radius: 10px;
    padding: 14px;
}

/* Notices (preview mode, hints) */
QLabel#previewNotice {
    background: @warning_soft@;
    color: #7A5308;
    border: 1px solid #F1DDA6;
    border-left: 4px solid #E8AB28;
    border-radius: 8px;
    padding: 10px 14px;
}
QLabel#infoNotice {
    background: @primary_soft@;
    color: #2A4A80;
    border: 1px solid #D6E3FB;
    border-left: 4px solid @primary@;
    border-radius: 8px;
    padding: 10px 14px;
}

/* =====================================================================
   Window title band (every module dialog)
   ===================================================================== */
QFrame#windowTitleBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @navy@, stop:1 @navy_2@);
    border: 1px solid @navy_line@;
    border-radius: 12px;
}
QLabel#windowTitle {
    color: @on_navy@;
    font-size: 16pt;
    font-weight: 700;
}
QLabel#windowSubtitle {
    color: @on_navy_muted@;
    font-size: 9pt;
}
QFrame#globalBrandedHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @navy@, stop:1 @navy_2@);
    border: 1px solid @navy_line@;
    border-radius: 12px;
}
QFrame#globalBrandPanel {
    background: @surface@;
    border: none;
    border-top-left-radius: 11px;
    border-bottom-left-radius: 11px;
}
QLabel#globalBrandFallback {
    color: @primary@;
    font-weight: 800;
}
QLabel#globalWindowTitle {
    color: @on_navy@;
    font-size: 14pt;
    font-weight: 700;
    padding: 10px 18px;
}

/* =====================================================================
   Buttons
   ===================================================================== */
QPushButton {
    background: @surface@;
    color: #1E3A6E;
    border: 1px solid @border_strong@;
    border-radius: 8px;
    padding: 9px 15px;
    font-weight: 600;
}
QPushButton:hover {
    background: #F2F6FD;
    border-color: @border_hover@;
    color: @navy@;
}
QPushButton:pressed {
    background: #E6EEFB;
}
QPushButton:focus {
    outline: none;
}
QPushButton:disabled {
    background: @surface_muted@;
    color: @text_soft@;
    border-color: @border@;
}
QPushButton#primaryButton, QPushButton#actionButton {
    background: @primary@;
    color: #FFFFFF;
    border: 1px solid @primary@;
    font-weight: 700;
}
QPushButton#primaryButton:hover, QPushButton#actionButton:hover {
    background: @primary_hover@;
    border-color: @primary_hover@;
    color: #FFFFFF;
}
QPushButton#primaryButton:pressed, QPushButton#actionButton:pressed {
    background: @primary_pressed@;
    border-color: @primary_pressed@;
}
QPushButton#primaryButton:disabled, QPushButton#actionButton:disabled {
    background: @primary_disabled@;
    border-color: @primary_disabled@;
    color: #F7F9FF;
}
QPushButton#primaryButton {
    padding: 9px 18px;
}
QPushButton#actionButton {
    padding: 6px 11px;
    border-radius: 7px;
}
QPushButton#secondaryButton, QPushButton#secondaryQuickAction {
    background: @surface@;
    color: #1E3A6E;
    border: 1px solid @border_strong@;
}
QPushButton#secondaryButton:hover, QPushButton#secondaryQuickAction:hover {
    background: @primary_soft@;
    border-color: #B9CCF3;
    color: @primary_hover@;
}
QPushButton#dangerButton {
    background: @surface@;
    color: @danger@;
    border: 1px solid #F1C4C4;
}
QPushButton#dangerButton:hover {
    background: @danger_soft@;
    border-color: @danger@;
    color: #B42318;
}
QPushButton#textAction {
    background: transparent;
    color: @primary@;
    border: none;
    padding: 2px 4px;
    font-size: 9pt;
    font-weight: 600;
}
QPushButton#textAction:hover {
    color: @primary_hover@;
    text-decoration: underline;
}
/* Square icon-only buttons inside table rows */
QPushButton#iconButton, QPushButton#viewCustomerButton, QPushButton#editCustomerButton {
    background: @primary@;
    border: 1px solid @primary@;
    border-radius: 8px;
    padding: 0px;
    margin: 0px;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
}
QPushButton#iconButton:hover, QPushButton#viewCustomerButton:hover, QPushButton#editCustomerButton:hover {
    background: @primary_hover@;
    border-color: @primary_hover@;
}
QPushButton#iconButton:pressed, QPushButton#viewCustomerButton:pressed, QPushButton#editCustomerButton:pressed {
    background: @primary_pressed@;
}
QDialogButtonBox QPushButton {
    min-width: 104px;
}

/* =====================================================================
   Inputs
   ===================================================================== */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit, QTimeEdit,
QDateTimeEdit, QSpinBox, QDoubleSpinBox {
    background: @surface@;
    color: @text_strong@;
    border: 1px solid @border_strong@;
    border-radius: 8px;
    padding: 8px 11px;
    min-height: 20px;
    selection-background-color: @primary@;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
QDateEdit:hover, QTimeEdit:hover, QDateTimeEdit:hover, QSpinBox:hover,
QDoubleSpinBox:hover {
    border-color: @border_hover@;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid @primary@;
    background: @surface@;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled,
QDateEdit:disabled, QTimeEdit:disabled, QDateTimeEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background: @surface_muted@;
    color: #526581;
    border-color: @border@;
}
QLineEdit[readOnly="true"], QTextEdit[readOnly="true"], QPlainTextEdit[readOnly="true"] {
    background: @surface_alt@;
}

/* Combo boxes and date pickers: blue trigger aligned with the spin-box steppers */
QComboBox, QDateEdit, QDateTimeEdit {
    padding-right: 36px;
}
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    border-left: 1px solid @primary_hover@;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
    background: @primary@;
}
QComboBox::drop-down:hover, QDateEdit::drop-down:hover, QDateTimeEdit::drop-down:hover {
    background: @primary_hover@;
}
QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow {
    image: url(@ICON_CHEVRON_WHITE@);
    width: 10px;
    height: 10px;
}
QComboBox::down-arrow:on {
    top: 1px;
}
QComboBox::drop-down:disabled, QDateEdit::drop-down:disabled {
    background: @primary_disabled@;
    border-left-color: @primary_disabled@;
}
QComboBox QAbstractItemView, QComboBox QListView {
    background: @surface@;
    color: @text_strong@;
    border: 1px solid @border_strong@;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: @primary_soft_2@;
    selection-color: @navy@;
}
QComboBox QAbstractItemView::item, QComboBox QListView::item {
    background: transparent;
    color: @text_strong@;
    min-height: 26px;
    padding: 5px 9px;
    border-radius: 5px;
}
QComboBox QAbstractItemView::item:hover, QComboBox QListView::item:hover {
    background: @primary_soft@;
}
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:selected:active,
QComboBox QAbstractItemView::item:selected:!active,
QComboBox QListView::item:selected {
    background: @primary_soft_2@;
    color: @navy@;
}

/* Spin boxes: established blue stepper buttons */
QSpinBox, QDoubleSpinBox {
    padding: 8px 32px 8px 11px;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    subcontrol-origin: border;
    width: 24px;
    border: none;
    border-left: 1px solid @primary_hover@;
    background: @primary@;
}
QAbstractSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 7px;
    border-bottom: 1px solid #4A79E8;
}
QAbstractSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 7px;
}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {
    background: @primary_hover@;
}
QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {
    background: @primary_pressed@;
}
QAbstractSpinBox::up-arrow {
    image: url(@ICON_SPIN_UP@);
    width: 9px;
    height: 9px;
}
QAbstractSpinBox::down-arrow {
    image: url(@ICON_SPIN_DOWN@);
    width: 9px;
    height: 9px;
}
QAbstractSpinBox::up-button:disabled, QAbstractSpinBox::down-button:disabled {
    background: @primary_disabled@;
}
/* Date edits keep their calendar trigger instead of steppers */
QDateEdit, QDateTimeEdit {
    padding: 8px 36px 8px 11px;
}

/* Check boxes and radio buttons */
QCheckBox, QRadioButton {
    spacing: 9px;
    color: #2B3F60;
    padding: 4px 2px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #B8C6D8;
    background: @surface@;
}
QCheckBox::indicator {
    border-radius: 5px;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: @primary@;
}
QCheckBox::indicator:checked {
    background: @primary@;
    border-color: @primary@;
    image: url(@ICON_CHECK@);
}
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #FFFFFF, stop:0.35 #FFFFFF, stop:0.42 @primary@, stop:1 @primary@);
    border-color: @primary@;
}
QCheckBox::indicator:disabled {
    background: @surface_muted@;
    border-color: @border@;
}
QCheckBox::indicator:checked:disabled {
    background: @primary_disabled@;
    border-color: @primary_disabled@;
}

/* Calendar popup */
QCalendarWidget QWidget {
    background: @surface@;
    color: @text_strong@;
    alternate-background-color: @surface_alt@;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: @primary@;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QCalendarWidget QToolButton {
    color: #FFFFFF;
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 6px 8px;
    font-weight: 700;
}
QCalendarWidget QToolButton:hover {
    background: @primary_hover@;
}
QCalendarWidget QToolButton::menu-indicator {
    image: none;
}
QCalendarWidget QSpinBox {
    background: @surface@;
    color: @text_strong@;
    border: 1px solid @border_strong@;
    border-radius: 5px;
    padding: 2px 4px;
}
QCalendarWidget QAbstractItemView {
    background: @surface@;
    color: @text_strong@;
    selection-background-color: @primary@;
    selection-color: #FFFFFF;
    outline: 0;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #B4BFCE;
}

/* =====================================================================
   Tables and lists
   ===================================================================== */
QAbstractItemView, QListView, QListWidget, QTreeView, QTreeWidget {
    background: @surface@;
    color: @text_strong@;
    alternate-background-color: @surface_alt@;
    selection-background-color: @primary_soft_2@;
    selection-color: @navy@;
    outline: 0;
}
QTableView, QTableWidget {
    background: @surface@;
    alternate-background-color: @surface_alt@;
    color: @text_strong@;
    border: 1px solid @border@;
    border-radius: 12px;
    gridline-color: #EEF2F7;
    selection-background-color: @primary_soft_2@;
    selection-color: @navy@;
    outline: 0;
}
QTableView::item, QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #EEF2F7;
}
QTableView::item:hover, QTableWidget::item:hover {
    background: #F2F6FE;
}
QTableView::item:selected, QTableWidget::item:selected,
QTableView::item:selected:active, QTableWidget::item:selected:active,
QTableView::item:selected:!active, QTableWidget::item:selected:!active {
    background: @primary_soft_2@;
    color: @navy@;
}
QAbstractItemView::item:selected, QListView::item:selected,
QListWidget::item:selected, QTreeView::item:selected {
    background: @primary_soft_2@;
    color: @navy@;
}
QHeaderView {
    background: transparent;
    border: none;
}
QHeaderView::section {
    background: @navy@;
    color: #FFFFFF;
    border: none;
    border-right: 1px solid #23406F;
    padding: 10px 10px;
    min-height: 20px;
    font-size: 9pt;
    font-weight: 700;
}
QHeaderView::section:horizontal:first {
    border-top-left-radius: 11px;
}
QHeaderView::section:horizontal:last {
    border-top-right-radius: 11px;
    border-right: none;
}
QHeaderView::section:horizontal:only-one {
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
}
QHeaderView::section:vertical {
    background: @surface_alt@;
    color: @text_muted@;
    border: none;
    border-bottom: 1px solid #EEF2F7;
    padding: 4px 8px;
    font-weight: 600;
}
QTableCornerButton::section {
    background: @navy@;
    border: none;
    border-top-left-radius: 11px;
}
QTableWidget QLineEdit {
    padding: 3px 6px;
    border-radius: 5px;
}

/* =====================================================================
   Tabs
   ===================================================================== */
QTabWidget::pane {
    background: transparent;
    border: none;
    border-top: 1px solid @border@;
    top: -1px;
    padding-top: 12px;
}
QTabWidget::tab-bar {
    left: 6px;
}
QTabBar {
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: @text_muted@;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 18px 9px 18px;
    margin-right: 4px;
    font-weight: 600;
}
QTabBar::tab:hover {
    color: @navy@;
    border-bottom-color: #C6D6F6;
}
QTabBar::tab:selected {
    color: @primary@;
    border-bottom-color: @primary@;
    font-weight: 700;
}
QTabWidget QWidget#qt_tabwidget_stackedwidget > QWidget {
    background: transparent;
}

/* =====================================================================
   Group boxes, cards and metric tiles
   ===================================================================== */
QGroupBox {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 8px 8px 8px;
    font-weight: 700;
    color: @navy@;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: @navy@;
    background: transparent;
}
QGroupBox QGroupBox {
    background: @surface_alt@;
    border-color: #E8EDF4;
}
QLabel#measureHeader {
    color: @navy@;
    background: @primary_soft@;
    border-radius: 5px;
    padding: 5px 4px;
    font-size: 8.5pt;
    font-weight: 700;
}
QLineEdit#measureInput, QComboBox#measureInput {
    padding: 4px 5px;
    min-height: 22px;
    border-radius: 6px;
}
/* Compact steppers: hiding spin buttons collapses the editor under a stylesheet, so keep them slim. */
QAbstractSpinBox#measureInput {
    padding: 4px 18px 4px 4px;
    min-height: 22px;
    border-radius: 6px;
}
QAbstractSpinBox#measureInput::up-button, QAbstractSpinBox#measureInput::down-button {
    width: 16px;
}
QAbstractSpinBox#measureInput::up-button {
    border-top-right-radius: 5px;
}
QAbstractSpinBox#measureInput::down-button {
    border-bottom-right-radius: 5px;
}
QAbstractSpinBox#measureInput::up-arrow, QAbstractSpinBox#measureInput::down-arrow {
    width: 7px;
    height: 7px;
}
QLabel#measureRowLabel {
    color: @navy@;
    font-weight: 700;
    padding-right: 4px;
}
QFrame#surfaceCard, QFrame#productFormCard, QFrame#productImageCard,
QFrame#priceSummaryCard, QFrame#templateCard {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
}
QFrame#templateCard {
    background: @surface_alt@;
}
QFrame#totalCard {
    background: @primary_soft@;
    border: 1px solid #D6E3FB;
    border-radius: 10px;
}
QLabel#totalValue {
    color: @navy@;
    font-size: 16pt;
    font-weight: 800;
}
QLabel#cardHeading {
    color: @navy@;
    font-size: 10.5pt;
    font-weight: 700;
}

/* Order pipeline stage chips */
QPushButton#stageChip {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
    padding: 0px;
    text-align: left;
}
QPushButton#stageChip:hover {
    border-color: #9DB8F2;
    background: #F7FAFF;
}
QPushButton#stageChip:checked {
    background: @primary_soft@;
    border: 2px solid @primary@;
}
QLabel#stageCount {
    font-size: 17pt;
    font-weight: 700;
}
QLabel#stageLabel {
    color: @text_muted@;
    font-size: 8.5pt;
    font-weight: 600;
}

/* Metric tiles used by Finance, Inventory and Customers */
QFrame#metricTile {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
}
QFrame#metricTile[tone="primary"] { border-left: 4px solid @primary@; }
QFrame#metricTile[tone="success"] { border-left: 4px solid @success@; }
QFrame#metricTile[tone="danger"]  { border-left: 4px solid @danger@; }
QFrame#metricTile[tone="warning"] { border-left: 4px solid #E8AB28; }
QFrame#metricTile[tone="navy"]    { border-left: 4px solid @navy@; }
QLabel#metricTileTitle {
    color: @text_muted@;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#metricTileValue {
    color: @text_strong@;
    font-size: 17pt;
    font-weight: 700;
}
QLabel#metricTileValue[tone="success"] { color: #0E8A5B; }
QLabel#metricTileValue[tone="danger"]  { color: #C03030; }
QLabel#metricTileValue[tone="warning"] { color: #9A6200; }
QLabel#metricTileValue[tone="primary"] { color: @primary_hover@; }
QLabel#metricTileHint {
    color: @text_soft@;
    font-size: 8.5pt;
}

/* =====================================================================
   Product editor
   ===================================================================== */
QWidget#productFormContent, QWidget#customerFormContent {
    background: transparent;
}
QLabel#priceSummaryLabel {
    color: @text_muted@;
    font-size: 8.5pt;
    font-weight: 700;
}
QLabel#priceSummaryValue {
    color: @primary@;
    font-size: 17pt;
    font-weight: 800;
}
QLabel#productImagePreview {
    background: @surface_alt@;
    color: @text_soft@;
    border: 1px dashed #B9C8DC;
    border-radius: 12px;
    font-size: 8.5pt;
    padding: 4px;
}

/* =====================================================================
   Scrollbars
   ===================================================================== */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 3px 2px 3px 0px;
}
QScrollBar::handle:vertical {
    background: #CBD5E3;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: #A6B5CB;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0px 3px 2px 3px;
}
QScrollBar::handle:horizontal {
    background: #CBD5E3;
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: #A6B5CB;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

/* =====================================================================
   Menus, message boxes, status bar, progress
   ===================================================================== */
QMenu {
    background: @surface@;
    color: @text_strong@;
    border: 1px solid @border_strong@;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    background: transparent;
    color: @text_strong@;
    padding: 7px 28px 7px 12px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: @primary_soft_2@;
    color: @navy@;
}
QMenu::item:disabled {
    color: @text_soft@;
}
QMenu::separator {
    height: 1px;
    background: @border@;
    margin: 4px 6px;
}
QMessageBox, QInputDialog {
    background: @surface@;
}
QMessageBox QLabel {
    color: @text_strong@;
    font-size: 9.5pt;
}
QStatusBar {
    background: @surface@;
    color: @text_muted@;
    border-top: 1px solid @border@;
    font-size: 8.5pt;
}
QStatusBar::item {
    border: none;
}
QProgressBar {
    background: @surface_muted@;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: @primary@;
    border-radius: 4px;
}

/* =====================================================================
   Application shell: navy sidebar, white topbar, light canvas
   ===================================================================== */
QFrame#appSidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @navy@, stop:1 #0C2149);
    border: none;
    border-right: 1px solid @navy_line@;
}
/* The menu scrolls on short screens; its layers stay transparent over the sidebar background. */
QScrollArea#sidebarScroll, QScrollArea#sidebarScroll > QWidget#qt_scrollarea_viewport,
QWidget#sidebarBody {
    background: transparent;
    border: none;
}
QScrollArea#sidebarScroll QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollArea#sidebarScroll QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.22);
    border-radius: 3px;
    min-height: 32px;
}
QScrollArea#sidebarScroll QScrollBar::add-line:vertical, QScrollArea#sidebarScroll QScrollBar::sub-line:vertical,
QScrollArea#sidebarScroll QScrollBar::add-page:vertical, QScrollArea#sidebarScroll QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0px;
}
QScrollArea#moduleScroll, QScrollArea#moduleScroll > QWidget#qt_scrollarea_viewport {
    background: transparent;
    border: none;
}
QLabel#sidebarLogo {
    background: @surface@;
    border-radius: 14px;
    padding: 6px;
}
QLabel#logoFallback {
    background: #244A83;
    color: #FFFFFF;
    border-radius: 12px;
    font-size: 14pt;
    font-weight: 800;
}
QLabel#sidebarSection {
    color: #AFC3E4;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 4px 10px;
}
QLabel#sidebarFooter {
    color: #DCE6F7;
    font-size: 7.5pt;
    font-weight: 600;
    padding: 10px 2px 2px 2px;
    border-top: 1px solid #23406F;
}
QPushButton#navButton {
    background: transparent;
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    padding: 8px 12px;
    text-align: left;
    font-size: 9.5pt;
    font-weight: 500;
}
QPushButton#navButton:hover {
    background: @primary@;
    color: #FFFFFF;
}
QPushButton#navButton:checked {
    background: @primary@;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton#navButton:checked:hover {
    background: @primary_hover@;
}
QFrame#workspace {
    background: @canvas@;
    border: none;
}
QFrame#topbar {
    background: @surface@;
    border: none;
    border-bottom: 1px solid @border@;
}
QWidget#dashboardPage, QWidget#transparentHost, QWidget#scrollHost {
    background: transparent;
}
QScrollArea#mainScroll {
    background: transparent;
    border: none;
}
QLineEdit#dashboardSearch {
    background: @surface_alt@;
    color: @text_strong@;
    border: 1px solid @border@;
    border-radius: 10px;
    padding: 9px 12px;
}
QLineEdit#dashboardSearch:hover {
    border-color: @border_strong@;
}
QLineEdit#dashboardSearch:focus {
    background: @surface@;
    border-color: @primary@;
}
QPushButton#topbarIconButton {
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 6px;
}
QPushButton#topbarIconButton:hover, QPushButton#topbarIconButton:checked {
    background: @primary_soft@;
}
QPushButton#profileChip {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 0px;
    text-align: left;
}
QPushButton#profileChip:hover {
    background: @surface_alt@;
    border-color: @border@;
}
QPushButton#profileChip:pressed {
    background: @primary_soft@;
    border-color: #D6E3FB;
}
QLabel#accountAvatar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @primary@, stop:1 @navy@);
    color: #FFFFFF;
    border-radius: 18px;
    font-size: 10.5pt;
    font-weight: 700;
}
QMenu#profileMenu {
    padding: 8px;
}
QMenu#profileMenu::item {
    padding: 9px 18px 9px 12px;
    border-radius: 8px;
}
QMenu#profileMenu::item:disabled {
    color: @text_strong@;
    font-weight: 700;
}
QLabel#profileName {
    color: @text_strong@;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#profileRole {
    color: @text_muted@;
    font-size: 8pt;
}

/* =====================================================================
   Dashboard
   ===================================================================== */
QFrame#welcomeBanner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:1 #EEF4FF);
    border: 1px solid @border@;
    border-radius: 14px;
}
QLabel#bannerGreeting {
    color: @text_muted@;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#bannerTitle {
    color: @navy@;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#bannerDescription {
    color: @text_muted@;
    font-size: 9pt;
}
QLabel#bannerSlogan {
    color: #1C396B;
    font-family: Arial, "Liberation Sans", Helvetica, sans-serif;
    font-size: 13pt;
    font-style: italic;
}
QLabel#bannerAccent {
    color: @primary@;
    font-size: 10pt;
}
QFrame#analyticsCard, QFrame#metricCard, QFrame#quickActionsCard {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 14px;
}
QLabel#cardTitle {
    color: @navy@;
    font-size: 10.5pt;
    font-weight: 700;
}
QLabel#actionHint {
    color: @text_muted@;
    font-size: 8.5pt;
}
QPushButton#quickTile {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
    padding: 2px;
    text-align: left;
}
QPushButton#quickTile:hover {
    background: #F7FAFF;
    border-color: #9DB8F2;
}
QLabel#quickTitle {
    color: @navy@;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#quickDescription {
    color: @text_muted@;
    font-size: 8.5pt;
}
QLabel#quickArrow {
    color: @primary@;
    font-size: 15pt;
}
QLabel#metricLabel {
    color: @text_muted@;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#metricValue {
    color: @text_strong@;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#metricGrowth {
    color: @success@;
    font-size: 8.5pt;
    font-weight: 700;
}
QComboBox#periodSelector {
    background: @surface@;
    color: #38557F;
    border: 1px solid @border@;
    border-radius: 8px;
    padding: 5px 30px 5px 10px;
    min-width: 62px;
}
QComboBox#periodSelector::drop-down {
    background: transparent;
    border: none;
    width: 24px;
}
QComboBox#periodSelector::down-arrow {
    image: url(@ICON_CHEVRON_BLUE@);
}
QLabel#legendDot {
    font-size: 10pt;
}
QLabel#legendLabel, QLabel#stockLabel {
    color: #40577D;
    font-size: 8.5pt;
}
QLabel#legendValue, QLabel#stockValue {
    color: #304B75;
    font-size: 8.5pt;
    font-weight: 700;
}
QLabel#productName, QLabel#activityTitle {
    color: #253D5D;
    font-size: 8.5pt;
    font-weight: 600;
}
QLabel#productCode, QLabel#activityDetail, QLabel#activityTime {
    color: #667A9B;
    font-size: 7.5pt;
}
QLabel#agendaDate {
    color: #27436E;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#agendaTime {
    color: #60799E;
    font-size: 8pt;
}
QFrame#promoCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7294B8, stop:0.45 #1F477A, stop:1 @navy@);
    border: 1px solid #294D7B;
    border-radius: 14px;
}
QLabel#promoTitle {
    color: #FFFFFF;
    font-size: 11pt;
    font-weight: 700;
}
QLabel#promoCaption {
    color: #D8E5F7;
    font-size: 7.5pt;
}
QLabel#statusDot {
    color: @success@;
}
QLabel#footerBrand {
    color: @text_soft@;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
}

/* Module cards (reusable component) */
QPushButton#moduleCard {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
    padding: 12px;
    text-align: left;
}
QPushButton#moduleCard:hover {
    background: #F8FAFF;
    border-color: #B9CCF3;
}
QLabel#moduleIcon {
    background: @primary_soft@;
    border: 1px solid #E2EBFC;
    border-radius: 14px;
}
QLabel#moduleTitle {
    color: @text_strong@;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#moduleDescription {
    color: @text_muted@;
    font-size: 8.5pt;
}
QLabel#moduleArrow {
    color: @primary@;
    font-size: 15pt;
}

/* =====================================================================
   Business analysis panel
   ===================================================================== */
QWidget#businessAnalysisPanel {
    background: transparent;
}
QLabel#aiEyebrow {
    color: #167E6A;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#aiPageTitle {
    color: @navy@;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#aiDescription, QLabel#aiSummary {
    color: @text_muted@;
    font-size: 9pt;
}
QFrame#aiFormCard, QFrame#aiLoadingCard, QFrame#aiResultsCard {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
}
QLabel#aiFieldLabel {
    color: #263B5E;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#aiCardTitle {
    color: @text_strong@;
    font-size: 13pt;
    font-weight: 700;
}
QLabel#aiStatusBadge {
    color: #167553;
    background: @success_soft@;
    border-radius: 10px;
    padding: 5px 11px;
    font-weight: 700;
}
QFrame#aiSkeleton, QFrame#aiSkeletonLine {
    background: #EDF2F8;
    border: none;
    border-radius: 8px;
}
QFrame#aiMetricCard {
    background: @surface_alt@;
    border: 1px solid #E6ECF5;
    border-radius: 10px;
}
QLabel#aiMetricLabel {
    color: @text_muted@;
    font-size: 9pt;
}
QLabel#aiMetricValue {
    color: @navy@;
    font-size: 17pt;
    font-weight: 800;
}

/* =====================================================================
   Sign-in (white label: logo + access card over a decorative backdrop)
   ===================================================================== */
QFrame#loginCard {
    background: @surface@;
    border: 1px solid rgba(255, 255, 255, 0.6);
    border-radius: 22px;
}
QLabel#loginLogo {
    background: transparent;
    padding: 0px;
}
QLabel#loginLogoFallback {
    color: @navy@;
    font-size: 18pt;
    font-weight: 800;
}
QLabel#loginFormTitle {
    color: @text_strong@;
    font-size: 20pt;
    font-weight: 700;
}
QLabel#loginFormSubtitle {
    color: @text_muted@;
    font-size: 9.5pt;
}
QLabel#loginFieldLabel {
    color: @text_strong@;
    font-size: 9pt;
    font-weight: 700;
}
QLineEdit#loginInput {
    background: @surface_alt@;
    border: 1px solid @border_strong@;
    border-radius: 11px;
    padding: 11px 13px;
    font-size: 10pt;
}
QLineEdit#loginInput:hover {
    border-color: @border_hover@;
}
QLineEdit#loginInput:focus {
    background: @surface@;
    border: 1px solid @primary@;
}
QLineEdit#loginInput:disabled {
    color: @text_muted@;
}
QLabel#loginCapsLock {
    color: #B7791F;
    font-size: 8.5pt;
    font-weight: 600;
}
QCheckBox#loginRemember {
    color: @text_muted@;
    font-size: 9pt;
}
QLabel#loginStatus {
    color: #B42318;
    background: #FEF3F2;
    border: 1px solid #FECDCA;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 9pt;
}
QFrame#loginCard QPushButton#primaryButton {
    border-radius: 11px;
    padding: 12px 18px;
    font-size: 10.5pt;
    font-weight: 700;
}
"""


def _qss_path(name: str) -> str:
    return (ASSETS / name).as_posix()


def build_stylesheet() -> str:
    stylesheet = THEME_QSS
    replacements = {
        "@ICON_SPIN_UP@": _qss_path("spin-up-white.svg"),
        "@ICON_SPIN_DOWN@": _qss_path("spin-down-white.svg"),
        "@ICON_CHEVRON_WHITE@": _qss_path("spin-down-white.svg"),
        "@ICON_CHEVRON_BLUE@": _qss_path("chevron-down-blue.svg"),
        "@ICON_CHECK@": _qss_path("check-white.svg"),
    }
    for token, value in replacements.items():
        stylesheet = stylesheet.replace(token, value)
    # Longest keys first so e.g. @primary_hover@ is not clobbered by @primary@.
    for key in sorted(PALETTE, key=len, reverse=True):
        stylesheet = stylesheet.replace(f"@{key}@", PALETTE[key])
    return stylesheet


def _light_palette() -> QPalette:
    """Light palette so native widgets never fall back to a dark system theme."""
    p = PALETTE
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: p["canvas"],
        QPalette.ColorRole.WindowText: p["text"],
        QPalette.ColorRole.Base: p["surface"],
        QPalette.ColorRole.AlternateBase: p["surface_alt"],
        QPalette.ColorRole.Text: p["text_strong"],
        QPalette.ColorRole.PlaceholderText: p["text_soft"],
        QPalette.ColorRole.Button: p["surface"],
        QPalette.ColorRole.ButtonText: p["navy"],
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: p["primary_soft_2"],
        QPalette.ColorRole.HighlightedText: p["navy"],
        QPalette.ColorRole.ToolTipBase: p["navy"],
        QPalette.ColorRole.ToolTipText: "#FFFFFF",
        QPalette.ColorRole.Link: p["primary"],
        QPalette.ColorRole.Light: "#FFFFFF",
        QPalette.ColorRole.Midlight: p["surface_alt"],
        QPalette.ColorRole.Mid: p["border_strong"],
        QPalette.ColorRole.Dark: p["border_hover"],
        QPalette.ColorRole.Shadow: "#9AA8BD",
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    disabled = QPalette.ColorGroup.Disabled
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(disabled, role, QColor(p["text_soft"]))
    return palette


def apply_theme(app: QApplication) -> None:
    font = QFont(FONT_FAMILY, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    app.setPalette(_light_palette())
    app.setStyleSheet(build_stylesheet())
