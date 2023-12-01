import os

from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsRectangle, QgsVectorLayer, QgsPointXY
from qgis.gui import QtCore
from qgis.utils import iface

from converter import field_names


from modules import pyqtgraph as pg


class HMGDataClassifier:
    def __init__(self, main: QDialog):
        self.chart_dialog = None
        self.main = main
        self.canvas = iface.mapCanvas()

        # ラムダ式でもconnectできる
        self.main.pushButton_cancel_3.clicked.connect(lambda: self.main.close())
        self.main.pushButton_classify.clicked.connect(self.classify_hmg_data)

        # Connect graphs
        self.main.classif_showgraph_kozui.clicked.connect(self.show_chart_kozui)
        # Set max break values
        self.main.classif_nbmax_kozui.setRange(1, 6)
        self.main.classif_nbmax_kozui.setValue(6)

    def classify_hmg_data(self):
        return

    def show_chart_kozui(self):
        x, y = self._get_mesh_chart_values(field_names.field_kozui)
        self._set_chart("DUMMY CHART", x, y)

    def _set_chart(self, chart_title, x_values, y_values):
        # Create a Pyqtgraph PlotWidget

        ## Switch to using white background and black foreground
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self.plot_widget = pg.plot(title=chart_title)

        # Add scatter plot to the Pyqtgraph PlotWidget
        scatter = pg.ScatterPlotItem(
            x=x_values,
            y=y_values,
            size=10,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(0, 0, 255),
        )
        self.plot_widget.addItem(scatter)

    def _get_mesh_chart_values(self, target_field):
        # default values
        x_values = [0]
        y_values = [0]
        # TO DO : condition if target field exists
        x_values = list(range(1, 30))
        y_values = [
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            5,
            3000,
            4566,
            4569,
            7898,
            8581,
            8888,
        ]
        return x_values, y_values
