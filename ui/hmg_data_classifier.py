import os

from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsRectangle, QgsVectorLayer, QgsPointXY
from qgis.gui import QtCore
from qgis.utils import iface

import constants


class HMGDataClassifier:
    def __init__(self, main: QDialog):
        self.main = main
        self.canvas = iface.mapCanvas()

        # ラムダ式でもconnectできる
        self.main.pushButton_cancel_3.clicked.connect(lambda: self.main.close())
        self.main.pushButton_classify.clicked.connect(self.classify_hmg_data)

        # Set max break values
        self.main.classif_nbmax_kozui.setRange(1, 6)
        self.main.classif_nbmax_kozui.setValue(6)

    def classify_hmg_data(self):
        return
