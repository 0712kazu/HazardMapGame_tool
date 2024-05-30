from ui.main_window import MainWindow


def test_cancel():
    main_window = MainWindow()
    main_window.show()
    assert main_window.isVisible() is True
    main_window.ui.pushButton_cancel.click()
    assert main_window.isVisible() is False
