from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject

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
        self.main.classif_showgraph_jisuberi.clicked.connect(self.show_chart_jisuberi)
        self.main.classif_showgraph_saigai.clicked.connect(self.show_chart_saigai)
        # Set max break values
        self.main.classif_nbmax_kozui.setRange(1, 6)
        self.main.classif_nbmax_kozui.setValue(6)

    def classify_hmg_data(self):
        return

    def show_chart_kozui(self):
        self._set_chart("洪水", field_names.field_kozui)

    def show_chart_jisuberi(self):
        self._set_chart("地すべり", field_names.field_jisuberi)

    def show_chart_saigai(self):
        self._set_chart("災害危険", field_names.field_saigai)

    def _set_chart(self, chart_title, target_field):
        mesh_score_layer = QgsProject.instance().mapLayersByName("mesh_score")[0]

        if target_field in mesh_score_layer.fields().names():
            field_values = [
                feature[target_field] for feature in mesh_score_layer.getFeatures()
            ]
            y_values = sorted(field_values)
            x_values = list(range(1, len(field_values) + 1))
        else:
            QMessageBox.information(
                None, "エラー", f"対象レイヤに{target_field}の属性がありません。"
            )
            return

        # Create a Pyqtgraph PlotWidget
        # Switch to using white background and black foreground
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self.plot_widget = pg.plot(title=chart_title)

        # Add scatter plot to the Pyqtgraph PlotWidget
        scatter = pg.ScatterPlotItem(
            x=x_values,
            y=y_values,
            size=5,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(0, 0, 255),
        )
        self.plot_widget.addItem(scatter)
