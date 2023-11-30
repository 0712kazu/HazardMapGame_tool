from qgis.core import QgsApplication
from qgis.gui import QgisInterface

from hmg_plugin import Sample
from preprocessor import Preprocessor
from hmg_data_generator import HMGDataGenerator


def test_show_menus(
    qgis_app: QgsApplication, qgis_iface: QgisInterface, plugin: Sample
):
    plugin.show_menu_01()
    assert isinstance(plugin.sample_menu_01, Preprocessor)

    plugin.show_menu_02()
    assert isinstance(plugin.sample_menu_02, HMGDataGenerator)
