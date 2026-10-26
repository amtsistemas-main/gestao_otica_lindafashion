import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_every_main_screen_opens(qapp):
    from ui.smoke import check_screens
    from ui.styles.theme import apply_theme

    apply_theme(qapp)
    assert check_screens(qapp) == []
