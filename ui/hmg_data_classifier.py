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
        self.hazards = ["kozui", "jisuberi", "saigai"]

        # ラムダ式でもconnectできる
        self.main.pushButton_cancel_3.clicked.connect(lambda: self.main.close())
        self.main.pushButton_classify.clicked.connect(self.classify_hmg_data)

        # self.main.classif_showgraph_kozui.clicked.connect(self.show_chart_kozui)
        # self.main.classif_showgraph_jisuberi.clicked.connect(self.show_chart_jisuberi)
        # self.main.classif_showgraph_saigai.clicked.connect(self.show_chart_saigai)

        for hazard in self.hazards:
            # Connect graphs
            show_graph_button = getattr(self.main, f"classif_showgraph_{hazard}")
            show_graph_function = getattr(self, f"show_chart_{hazard}")
            show_graph_button.clicked.connect(show_graph_function)

            # Set max break values
            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            nbmax_box.setRange(1, 10)
            nbmax_box.setValue(10)
            # nbmax_box.valueChanged.connect()
            for n in range(1, 11):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percentage_box.setRange(1, 100)
                percentage_box.setValue(n * 10)

    def classify_hmg_data(self):
        return

    def show_chart_kozui(self):
        self._set_chart("洪水", field_names.field_kozui)

    def show_chart_jisuberi(self):
        self._set_chart("地すべり", field_names.field_jisuberi)

    def show_chart_saigai(self):
        self._set_chart("災害危険", field_names.field_saigai)

    def _set_chart(self, chart_title: str, target_field: str) -> None:
        mesh_score_layer = QgsProject.instance().mapLayersByName("mesh_score")[0]

        if target_field in mesh_score_layer.fields().names():
            field_values = [
                feature[target_field] for feature in mesh_score_layer.getFeatures()
            ]
            y_values = sorted(field_values)
            x_values = list(range(1, len(field_values) + 1))
        else:
            error_message = f"対象レイヤに{target_field}の属性がありません。"
            QMessageBox.information(None, "エラー", error_message)
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
            name=chart_title,
        )
        self.plot_widget.addItem(scatter)
        self.plot_widget.getPlotItem().getViewBox().setRange(yRange=[0, max(y_values)])

        plot2 = pg.ViewBox()
        self.plot_widget.scene().addItem(plot2)
        self.plot_widget.hideAxis("right")
        self.plot_widget.getAxis("right").linkToView(plot2)
        self.plot_widget.getPlotItem().layout.addItem(plot2, 2, 1)
        plot2.setXLink(self.plot_widget.getPlotItem())
        plot2.setRange(yRange=[0, 100])

        percent1 = self.plot_widget.plot([0, 96], [50, 50], pen="r", name="percent1")
        plot2.addItem(percent1)
        percent2 = self.plot_widget.plot([0, 96], [80, 80], pen="r", name="percent2")
        plot2.addItem(percent2)

        # Set axis labels
        self.plot_widget.setLabel("bottom", "メッシュ数", color="black")
        self.plot_widget.setLabel("left", "体積", color="blue")
        self.plot_widget.setLabel("right", "比率", color="red")
