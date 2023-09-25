import os

from PyQt5.QtWidgets import QDialog
from qgis.PyQt import uic

from .hmg_data_generator import HGMDataGenerator
from .preprocessor import Preprocessor


class MainWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(
            os.path.join(os.path.dirname(__file__), "main_window.ui"), self
        )

        self.hmg_data_generator = HGMDataGenerator(self)
        self.preprocessor = Preprocessor(self)
