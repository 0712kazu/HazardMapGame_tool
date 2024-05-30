from hmg_plugin import HmgPlugin
from ui.main_window import MainWindow


def test_show_menu(plugin: HmgPlugin):
    plugin.show_data_generator_window()
    assert isinstance(plugin.show_data_generator_window, MainWindow)
