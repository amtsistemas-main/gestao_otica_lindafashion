"""A barcode reader types the code and sends Enter: that Enter must not press dialog buttons."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from ui.components.window_header import install_window_headers

    app = QApplication.instance() or QApplication([])
    if app.property("_enter_key_guard") is None:
        install_window_headers(app)
    return app


def _scan(app, field, code):
    field.setFocus()
    app.processEvents()
    QTest.keyClicks(field, code)
    QTest.keyClick(field, Qt.Key.Key_Return)
    app.processEvents()


def _dialog_with_field(own_action: bool):
    from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout

    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    field, button = QLineEdit(), QPushButton("Salvar")
    layout.addWidget(field)
    layout.addWidget(button)
    hits = []
    if own_action:
        field.returnPressed.connect(lambda: hits.append("campo"))
    button.clicked.connect(lambda: hits.append("botão"))
    dialog.show()
    return dialog, field, hits


def test_field_with_its_own_enter_action_keeps_the_enter(qapp):
    dialog, field, hits = _dialog_with_field(own_action=True)
    _scan(qapp, field, "7891234567890")
    assert hits == ["campo"]
    dialog.close()


def test_plain_form_field_still_saves_on_enter(qapp):
    dialog, field, hits = _dialog_with_field(own_action=False)
    _scan(qapp, field, "texto")
    assert hits == ["botão"]
    dialog.close()


def test_pos_scans_add_items_and_keep_focus(qapp):
    from PySide6.QtWidgets import QDialog

    from modules.sales.pos import PosDialog
    from modules.settings.service import StoreSettings

    pos = PosDialog(None, StoreSettings())
    pos.showNormal()
    clicked = []
    for button in pos.findChildren(type(pos.finish_button)):
        button.clicked.connect(lambda _c=False, b=button: clicked.append(b.text()))
    _scan(qapp, pos.product_search, "7891234567890")
    _scan(qapp, pos.product_search, "7891234567890")
    assert len(pos._lines) == 1 and pos._lines[0].quantity == 2
    assert clicked == [] and pos.product_search.text() == "" and pos.product_search.hasFocus()
    assert QDialog.result(pos) == 0 and pos.isVisible()
    pos.done(0)


def test_product_form_barcode_jumps_to_next_field(qapp):
    from modules.products.page import ProductFormDialog

    form = ProductFormDialog()
    form.show()
    _scan(qapp, form.barcode, "7890000000999")
    assert form.isVisible() and form.result() == 0
    assert form.barcode.text() == "7890000000999" and not form.barcode.hasFocus()
    form.done(0)
