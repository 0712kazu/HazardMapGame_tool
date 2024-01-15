from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsProject,
    QgsMapLayerProxyModel,
    QgsField,
    QgsFeatureRequest,
)

from qgis.utils import iface

from converter.mesh_score_classifier import (
    graduate_layer,
    get_mesh_value_from_percentage,
    get_color_from_range,
    classify_values_stdev,
    classify_values_tcg,
    get_tcg_ranks,
)
import constants
from modules import pyqtgraph as pg


class HMGDataClassifier:
    def __init__(self, main: QDialog):
        self.plot_widget = None
        self.main = main
        self.canvas = iface.mapCanvas()
        self.hazards = ["tornado", "kozui", "jisuberi", "saigai", "sediments"]

        # Target mesh layer にする
        self.main.mesh_score_layer_combobox.setFilters(
            QgsMapLayerProxyModel.PolygonLayer
        )

        if len(QgsProject.instance().mapLayersByName("mesh_score")) > 0:
            self.main.mesh_score_layer_combobox.setLayer(
                QgsProject.instance().mapLayersByName("mesh_score")[0]
            )

        # ラムダ式でもconnectできる
        self.main.pushButton_cancel_3.clicked.connect(lambda: self.main.close())
        self.main.pushButton_tcg_classify.clicked.connect(self.classify_data_tcg)

        for hazard in self.hazards:
            # Connect graphs
            show_graph_button = getattr(self.main, f"classif_showgraph_{hazard}")
            show_graph_function = getattr(self, f"on_number_changed_{hazard}")
            show_graph_button.clicked.connect(show_graph_function)

            # Set max break values to 10 as default
            on_number_changed_function = getattr(self, f"on_number_changed_{hazard}")
            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            nbmax_box.setRange(1, 10)
            nbmax_box.setValue(10)
            nbmax_box.valueChanged.connect(on_number_changed_function)

            # default percentages: 10 classes by 10%
            for n in range(1, 11):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percentage_box.setRange(0, 100)
                percentage_box.setValue(n * 10)
                percentage_box.valueChanged.connect(on_number_changed_function)

            # set classifications methods
            # standard deviation
            stdev_button = getattr(self.main, f"radiobutton_stdev_{hazard}")
            stdev_function = getattr(self, f"classify_stdev_{hazard}")
            stdev_button.clicked.connect(stdev_function)

            # tcg classifier
            tcg_button = getattr(self.main, f"radiobutton_tcg_{hazard}")
            tcg_function = getattr(self, f"classify_tcg_{hazard}")
            tcg_button.clicked.connect(tcg_function)

            # custom button
            custom_button = getattr(self.main, f"radiobutton_custom_{hazard}")
            custom_button.setChecked(True)  # default button
            custom_button.clicked.connect(on_number_changed_function)

    def on_number_changed_tornado(self):
        self._set_percentages("tornado")
        self.show_chart_tornado()

    def on_number_changed_kozui(self):
        self._set_percentages("kozui")
        self.show_chart_kozui()

    def on_number_changed_sediments(self):
        self._set_percentages("sediments")
        self.show_chart_sediments()

    def on_number_changed_jisuberi(self):
        self._set_percentages("jisuberi")
        self.show_chart_jisuberi()

    def on_number_changed_saigai(self):
        self._set_percentages("saigai")
        self.show_chart_saigai()

    def _set_percentages(self, hazard: str):
        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
        custom_radio_btn = getattr(self.main, f"radiobutton_custom_{hazard}")
        stdev_radio_btn = getattr(self.main, f"radiobutton_stdev_{hazard}")
        tcg_radio_btn = getattr(self.main, f"radiobutton_tcg_{hazard}")

        if stdev_radio_btn.isChecked():
            nbmax_box.setReadOnly(False)
            self._set_percentages_stdev(hazard)

        if tcg_radio_btn.isChecked():
            nbmax_box.setReadOnly(True)
            self._set_percentages_tcg(hazard)

        if custom_radio_btn.isChecked():
            nbmax_box.setReadOnly(False)

        for n in range(1, 11):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")

            # lock box if box ID >=  designated max box
            # and if classification method is not custom
            if n > nbmax_box.value():
                percentage_box.setValue(0)
                percentage_box.setReadOnly(True)
            elif custom_radio_btn.isChecked() is False:
                # lock if it is not custom mode
                percentage_box.setReadOnly(True)
            else:
                percentage_box.setReadOnly(False)

            # set digits rules for custom classification
            if custom_radio_btn.isChecked():
                # set 100 as max value
                if n == nbmax_box.value():
                    percentage_box.setValue(100)
                # TBC: make digit to be up to previous one
                # TO DO: set nbmax_box = n when 100% is written (now bugging)

    def classify_stdev_tornado(self):
        self._set_percentages_stdev("tornado")

    def classify_stdev_kozui(self):
        self._set_percentages_stdev("kozui")

    def classify_stdev_sediments(self):
        self._set_percentages_stdev("sediments")

    def classify_stdev_jisuberi(self):
        self._set_percentages_stdev("jisuberi")

    def classify_stdev_saigai(self):
        self._set_percentages_stdev("saigai")

    def _set_percentages_stdev(self, hazard: str):
        mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()
        # get mesh_score target field name
        target_field = getattr(constants, f"field_{hazard}")

        if target_field in mesh_score_layer.fields().names():
            field_values = [
                feature[target_field] for feature in mesh_score_layer.getFeatures()
            ]
            y_values = sorted(field_values)
        else:
            error_message = f"対象レイヤに{target_field}の属性がありません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
        percentages_classes = classify_values_stdev(y_values, nbmax_box.value())

        if len(percentages_classes) != nbmax_box.value():
            nbmax_box.setValue(len(percentages_classes))

        for n in range(1, len(percentages_classes) + 1):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            percentage_box.setValue(percentages_classes[n - 1])

    def classify_tcg_tornado(self):
        self._set_percentages_tcg("tornado")

    def classify_tcg_kozui(self):
        self._set_percentages_tcg("kozui")

    def classify_tcg_sediments(self):
        self._set_percentages_tcg("sediments")

    def classify_tcg_jisuberi(self):
        self._set_percentages_tcg("jisuberi")

    def classify_tcg_saigai(self):
        self._set_percentages_tcg("saigai")

    def _set_percentages_tcg(self, hazard):
        mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

        # get mesh_score target field name
        target_field = getattr(constants, f"field_{hazard}")

        if target_field in mesh_score_layer.fields().names():
            field_values = [
                feature[target_field] for feature in mesh_score_layer.getFeatures()
            ]
            y_values = sorted(field_values)

        else:
            error_message = f"対象レイヤに{target_field}の属性がありません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")

        # test if all are equals
        equal_values = y_values.count(y_values[0]) == len(y_values)
        if equal_values:
            nbmax_box.setValue(1)
            nbmax_box.setReadOnly(True)
            percentage_box = getattr(self.main, f"classif_percent_1_{hazard}")
            percentage_box.setValue(100)
            return

        # classify if values are not equals
        percentages_classes = classify_values_tcg(y_values)

        if len(percentages_classes) != nbmax_box.value():
            nbmax_box.setValue(len(percentages_classes))

        # update UI
        nbmax_box.setReadOnly(True)

        for n in range(1, len(percentages_classes) + 1):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            percentage_box.setValue(percentages_classes[n - 1])

    def show_chart_tornado(self):
        self._set_chart("竜巻", "tornado")

    def show_chart_kozui(self):
        self._set_chart("洪水", "kozui")

    def show_chart_sediments(self):
        self._set_chart("土砂", "sediments")

    def show_chart_jisuberi(self):
        self._set_chart("地すべり", "jisuberi")

    def show_chart_saigai(self):
        self._set_chart("災害危険", "saigai")

    def _handle_plot_close(self, event):
        # Set the flag to indicate that the plot has been closed
        self.plot_widget = None
        event.accept()

    def _set_chart(self, chart_title: str, hazard: str) -> None:
        mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

        # get mesh_score target field name
        target_field = getattr(constants, f"field_{hazard}")

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

        if self.plot_widget:
            # if plot exists, update
            self.plot_widget.clear()
        else:
            # If plot not exists Create a Pyqtgraph PlotWidget
            # Switch to using white background and black foreground
            pg.setConfigOption("background", "w")
            pg.setConfigOption("foreground", "k")
            self.plot_widget = pg.plot(title="HMGデータグラフ")
            self.plot_widget.closeEvent = self._handle_plot_close

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

        # Set axis labels
        self.plot_widget.setLabel("bottom", "メッシュ数", color="black")
        self.plot_widget.setLabel("left", "体積", color="blue")

        # set title
        self.plot_widget.setTitle(chart_title)

        # set default minimum class as 0.001
        # under minimum is set transparent

        breaks = [[0, constants.MAP_MIN_VALUE, "transparent"]]
        break_min = 0
        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")

        for n in range(1, nbmax_box.value() + 1):
            percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
            percent_value = percentage_box.value()

            # get mesh value from percentage
            break_max = get_mesh_value_from_percentage(y_values, percent_value)

            # get color to show in graph and map
            color = get_color_from_range(n, nbmax_box.value())

            # add break_max line as plot
            line_label = f"{percent_value}% ({round(break_max,1)})"
            percent_line = self.plot_widget.plot(
                [0, len(y_values)],
                [break_max, break_max],
                pen=pg.mkPen(color, width=2),
                name=line_label,
            )
            # labeling
            label_item = pg.TextItem(text=line_label, color=color)
            self.plot_widget.addItem(label_item)
            label_item.setPos(0, break_max)

            self.plot_widget.addItem(percent_line)

            # calculate break for maps
            breaks.append([break_min, break_max, color])
            break_min = break_max

        # reflect to map
        graduate_layer(mesh_score_layer, target_field, breaks)

    def classify_data_tcg(self):
        # list of added fields
        tcg_rank_fields_added = []

        mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

        for hazard in self.hazards:
            # get mesh_score target field name
            target_field = getattr(constants, f"field_{hazard}")

            if target_field in mesh_score_layer.fields().names():
                field_values = [
                    feature[target_field] for feature in mesh_score_layer.getFeatures()
                ]
                y_values = sorted(field_values)
            else:
                continue
            # get ranks from values
            tcg_ranks = get_tcg_ranks(y_values)
            print(tcg_ranks)
            tcg_rank_field = f"t_{target_field}"

            # add tcg rank field if not exists
            if tcg_rank_field not in mesh_score_layer.fields().names():
                mesh_score_layer.startEditing()
                mesh_score_layer.addAttribute(QgsField(tcg_rank_field, QVariant.Int))
                mesh_score_layer.commitChanges()

            # calculate tcg rank
            mesh_score_layer.startEditing()
            # input y_values to be in ascending order :[0,10,255,3598,3699,8555]
            # associated tcg_ranks : [0,1,2,4,4,6]
            # Sort the features based on hazard score ascending order
            request = QgsFeatureRequest().addOrderBy(target_field, ascending=True)
            features = mesh_score_layer.getFeatures(request)

            # Update the tcg rank field based on the sorting order
            for index, feature in enumerate(features):
                feature.setAttribute(tcg_rank_field, tcg_ranks[index])
                print(tcg_ranks[index])
                mesh_score_layer.updateFeature(feature)

            # Stop editing and save changes
            mesh_score_layer.commitChanges()

            tcg_rank_fields_added.append(tcg_rank_field)

        # message end
        message = "TCG方式での点数化が完了しました。\n計算した属性:\n"
        for tcg_field in tcg_rank_fields_added:
            message += f"{tcg_field}\n"
        QMessageBox.information(None, "完了", message)
