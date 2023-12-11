from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject

from qgis.utils import iface

from converter import field_names
from converter.mesh_score_symbolizer import (
    graduate_layer,
    get_mesh_value_from_percentage,
    get_color_from_range,
)
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

        for hazard in self.hazards:
            # Connect graphs
            show_graph_button = getattr(self.main, f"classif_showgraph_{hazard}")
            show_graph_function = getattr(self, f"show_chart_{hazard}")
            show_graph_button.clicked.connect(show_graph_function)

            # Set max break values
            on_number_changed_function = getattr(self, f"on_number_changed_{hazard}")
            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            nbmax_box.setRange(1, 10)
            nbmax_box.setValue(10)
            nbmax_box.valueChanged.connect(on_number_changed_function)
            # set box per 10% as default
            for n in range(1, 11):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percentage_box.setRange(0, 100)
                percentage_box.setValue(n * 10)
                percentage_box.valueChanged.connect(on_number_changed_function)

    def classify_hmg_data(self):
        return

    def on_number_changed_kozui(self):
        self._set_percentages("kozui")

    def on_number_changed_jisuberi(self):
        self._set_percentages("jisuberi")

    def on_number_changed_saigai(self):
        self._set_percentages("saigai")

    def _set_percentages(self, hazard: str):
        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
        for n in range(1, 11):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            if n > nbmax_box.value():
                percentage_box.setValue(0)
                percentage_box.setReadOnly(True)
            else:
                percentage_box.setReadOnly(False)

    def show_chart_kozui(self):
        self._set_chart("洪水", "kozui")

    def show_chart_jisuberi(self):
        self._set_chart("地すべり", "jisuberi")

    def show_chart_saigai(self):
        self._set_chart("災害危険", "saigai")

    def _set_chart(self, chart_title: str, hazard: str) -> None:
        mesh_score_layer = QgsProject.instance().mapLayersByName("mesh_score")[0]

        # get mesh_score target field name
        target_field = getattr(field_names, f"field_{hazard}")

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

        # set second chart for percentages
        plot2 = pg.ViewBox()
        self.plot_widget.scene().addItem(plot2)
        self.plot_widget.hideAxis("right")
        self.plot_widget.getAxis("right").linkToView(plot2)
        self.plot_widget.getPlotItem().layout.addItem(plot2, 2, 1)
        plot2.setXLink(self.plot_widget.getPlotItem())
        plot2.setRange(yRange=[0, 100])

        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
        for n in range(1, nbmax_box.value() + 1):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            percent_value = percentage_box.value()
            percent_line = self.plot_widget.plot(
                [0, 96],
                [percent_value, percent_value],
                pen="r",
                name=f"{chart_title}_比率_{n}",
            )
            plot2.addItem(percent_line)

        # Set axis labels
        self.plot_widget.setLabel("bottom", "メッシュ数", color="black")
        self.plot_widget.setLabel("left", "体積", color="blue")
        self.plot_widget.setLabel("right", "比率", color="red")

        # calculate breaks for maps
        breaks = []
        break_min = 0
        for n in range(1, nbmax_box.value() + 1):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            percent_value = percentage_box.value()
            break_max = get_mesh_value_from_percentage(y_values, percent_value)
            color = get_color_from_range(n, nbmax_box.value())
            print([break_min, break_max, color])
            breaks.append([break_min, break_max, color])
            break_min = break_max

        # reflect to map
        graduate_layer(mesh_score_layer, target_field, breaks)
