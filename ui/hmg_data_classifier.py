import os

from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsRectangle, QgsVectorLayer, QgsPointXY
from qgis.gui import QtCore
from qgis.utils import iface

from converter import field_names
from ui.chart_dialog import ChartDialog


class HMGDataClassifier:
    def __init__(self, main: QDialog):
        self.chart_dialog = None
        self.main = main
        self.canvas = iface.mapCanvas()

        # ラムダ式でもconnectできる
        self.main.pushButton_cancel_3.clicked.connect(lambda: self.main.close())
        self.main.pushButton_classify.clicked.connect(self.classify_hmg_data)

        # Connect graphs
        self.main.classif_showgraph_kozui.clicked.connect(self.show_graph_kozui)
        # Set max break values
        self.main.classif_nbmax_kozui.setRange(1, 6)
        self.main.classif_nbmax_kozui.setValue(6)

    def classify_hmg_data(self):
        return

    def show_graph_kozui(self):
        if self.chart_dialog is None:
            self.chart_dialog = ChartDialog()

        self.chart_dialog.show()
