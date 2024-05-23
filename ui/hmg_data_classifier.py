from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsMapLayerProxyModel,
    QgsField,
    QgsFeatureRequest,
)

from qgis.utils import iface
from PyQt5.QtCore import QVariant

from converter.mesh_score_classifier import (
    graduate_layer,
    get_mesh_value_from_percentage,
    get_color_from_range,
    classify_values_stdev,
    classify_values_tcg,
    get_tcg_ranks,
)

import constants
from utils import add_to_map
from modules import pyqtgraph as pg


class HMGDataClassifier:
    def __init__(self, main: QDialog):
        self.plot_widget = None
        self.main = main
        self.canvas = iface.mapCanvas()

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
        self.main.pushButton_classify.clicked.connect(self._set_classified_hazard_score)

        # stdev calculation flag to make calculate only once
        self.stdev_calculating = False

        # Custom method Sum surfaces as Default
        self.main.btn_custom_calc_sumsurf.setChecked(True)

        for hazard in constants.hazards_ui_names:
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
            for n in range(0, 11):
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

    def on_number_changed_tsunami(self):
        self._set_percentages("tsunami")
        self.show_chart_tsunami()

    def on_number_changed_jisuberi(self):
        self._set_percentages("jisuberi")
        self.show_chart_jisuberi()

    def on_number_changed_saigai(self):
        self._set_percentages("saigai")
        self.show_chart_saigai()

    def on_number_changed_surge(self):
        self._set_percentages("surge")
        self.show_chart_surge()

    def on_number_changed_earthquake(self):
        self._set_percentages("earthquake")
        self.show_chart_earthquake()

    def on_number_changed_slope(self):
        self._set_percentages("slope")
        self.show_chart_slope()

    def on_number_changed_refuge(self):
        self._set_percentages("refuge")
        self.show_chart_refuge()

    def on_number_changed_custom(self):
        self._set_percentages("custom")
        self.show_chart_custom()

    def _set_percentages(self, hazard: str):
        nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
        custom_radio_btn = getattr(self.main, f"radiobutton_custom_{hazard}")
        stdev_radio_btn = getattr(self.main, f"radiobutton_stdev_{hazard}")
        tcg_radio_btn = getattr(self.main, f"radiobutton_tcg_{hazard}")

        try:
            if stdev_radio_btn.isChecked() and not self.stdev_calculating:
                nbmax_box.setReadOnly(False)
                self._set_percentages_stdev(hazard)

            if tcg_radio_btn.isChecked():
                nbmax_box.setReadOnly(True)
                self.set_percentages_tcg(hazard)

            if custom_radio_btn.isChecked():
                nbmax_box.setReadOnly(False)

            for n in range(0, 11):
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

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def classify_stdev_tornado(self):
        self._set_percentages_stdev("tornado")

    def classify_stdev_kozui(self):
        self._set_percentages_stdev("kozui")

    def classify_stdev_sediments(self):
        self._set_percentages_stdev("sediments")

    def classify_stdev_tsunami(self):
        self._set_percentages_stdev("tsunami")

    def classify_stdev_jisuberi(self):
        self._set_percentages_stdev("jisuberi")

    def classify_stdev_saigai(self):
        self._set_percentages_stdev("saigai")

    def classify_stdev_surge(self):
        self._set_percentages_stdev("surge")

    def classify_stdev_earthquake(self):
        self._set_percentages_stdev("earthquake")

    def classify_stdev_slope(self):
        self._set_percentages_stdev("slope")

    def classify_stdev_refuge(self):
        self._set_percentages_stdev("refuge")

    def classify_stdev_custom(self):
        self._set_percentages_stdev("custom")

    def _set_percentages_stdev(self, hazard: str):
        if not self.main.mesh_score_layer_combobox.currentLayer():
            error_message = "対象HMGデータレイヤ(例：mesh_score)が足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        try:
            mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()
            # get mesh_score target field name
            if hazard == "custom":
                target_field = self.main.custom_hmg_fieldname.text()
            else:
                target_field = getattr(constants, f"field_{hazard}")

            if target_field in mesh_score_layer.fields().names():
                field_values = [
                    feature[target_field] for feature in mesh_score_layer.getFeatures()
                ]
                y_values = sorted(field_values)
            else:
                error_message = f"対象レイヤに「{target_field}」の属性がありません。"
                QMessageBox.information(None, "エラー", error_message)
                return

            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            percentages_classes = classify_values_stdev(y_values, nbmax_box.value())

            if len(percentages_classes) - 1 != nbmax_box.value():
                self.stdev_calculating = True
                nbmax_box.setValue(len(percentages_classes) - 1)

            for n in range(0, len(percentages_classes)):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percentage_box.setValue(percentages_classes[n])

            self.stdev_calculating = False

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def classify_tcg_tornado(self):
        self.set_percentages_tcg("tornado")

    def classify_tcg_kozui(self):
        self.set_percentages_tcg("kozui")

    def classify_tcg_sediments(self):
        self.set_percentages_tcg("sediments")

    def classify_tcg_tsunami(self):
        self.set_percentages_tcg("tsunami")

    def classify_tcg_jisuberi(self):
        self.set_percentages_tcg("jisuberi")

    def classify_tcg_saigai(self):
        self.set_percentages_tcg("saigai")

    def classify_tcg_surge(self):
        self.set_percentages_tcg("surge")

    def classify_tcg_earthquake(self):
        self.set_percentages_tcg("earthquake")

    def classify_tcg_slope(self):
        self.set_percentages_tcg("slope")

    def classify_tcg_refuge(self):
        self.set_percentages_tcg("refuge")

    def classify_tcg_custom(self):
        self.set_percentages_tcg("custom")

    def set_percentages_tcg(self, hazard):
        if not self.main.mesh_score_layer_combobox.currentLayer():
            error_message = "対象HMGデータレイヤ(例：mesh_score)が足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        try:
            mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

            # get mesh_score target field name
            if hazard == "custom":
                target_field = self.main.custom_hmg_fieldname.text()
            else:
                target_field = getattr(constants, f"field_{hazard}")

            if target_field in mesh_score_layer.fields().names():
                field_values = [
                    feature[target_field] for feature in mesh_score_layer.getFeatures()
                ]
                y_values = sorted(field_values)

            else:
                error_message = f"対象レイヤに「{target_field}」の属性がありません。"
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

            if len(percentages_classes) - 1 != nbmax_box.value():
                nbmax_box.setValue(len(percentages_classes) - 1)

            # update UI
            nbmax_box.setReadOnly(True)

            for n in range(0, len(percentages_classes)):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percentage_box.setValue(percentages_classes[n])

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def show_chart_tornado(self):
        self._set_chart("竜巻", "tornado")

    def show_chart_kozui(self):
        self._set_chart("洪水", "kozui")

    def show_chart_sediments(self):
        self._set_chart("土砂", "sediments")

    def show_chart_tsunami(self):
        self._set_chart("津波", "tsunami")

    def show_chart_jisuberi(self):
        self._set_chart("地すべり", "jisuberi")

    def show_chart_saigai(self):
        self._set_chart("災害危険", "saigai")

    def show_chart_surge(self):
        self._set_chart("高潮", "surge")

    def show_chart_earthquake(self):
        self._set_chart("地震", "earthquake")

    def show_chart_slope(self):
        self._set_chart("傾斜度", "slope")

    def show_chart_refuge(self):
        self._set_chart("避難施設", "refuge")

    def show_chart_custom(self):
        self._set_chart(self.main.custom_hmg_seamlessfilename.text(), "custom")

    def _handle_plot_close(self, event):
        # Set the flag to indicate that the plot has been closed
        self.plot_widget = None
        event.accept()

    def _display_only(self, prefix: str, hazard_name: str) -> None:
        """display only input layer {prefix}_{hazard_name},
        turn off other prefix 'prefix_○○' ones"""
        layer_tree = QgsProject.instance().layerTreeRoot()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == f"{prefix}_{hazard_name}":
                layer_tree.findLayer(layer.id()).setItemVisibilityChecked(True)
            elif prefix in layer.name():
                layer_tree.findLayer(layer.id()).setItemVisibilityChecked(False)

    def _set_chart(self, chart_title: str, hazard: str) -> None:
        if not self.main.mesh_score_layer_combobox.currentLayer():
            error_message = "対象HMGデータレイヤ(例：mesh_score)が足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        try:
            mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

            # get mesh_score target field name
            if hazard == "custom":
                target_field = self.main.custom_hmg_fieldname.text()
            else:
                target_field = getattr(constants, f"field_{hazard}")

            if target_field in mesh_score_layer.fields().names():
                field_values = [
                    feature[target_field] for feature in mesh_score_layer.getFeatures()
                ]
                y_values = sorted(field_values)
                x_values = list(range(1, len(field_values) + 1))
            else:
                error_message = f"対象レイヤに「{target_field}」の属性がありません。"
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
            self.plot_widget.getPlotItem().getViewBox().setRange(
                yRange=[0, max(y_values)]
            )

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

            for n in range(0, nbmax_box.value() + 1):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percent_value = percentage_box.value()

                # get mesh value from percentage
                break_max = get_mesh_value_from_percentage(y_values, percent_value)
                # first value should be the last 0 value
                if break_max > 0 and n == 0:
                    break_max = 0

                # get color to show in graph and map
                color = get_color_from_range(n + 1, nbmax_box.value() + 1)

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

            # reflect to hazard mesh layer
            # create if not exists
            if not QgsProject.instance().mapLayersByName(f"mesh_score_{target_field}"):
                add_layer = mesh_score_layer.clone()
                add_to_map(add_layer, f"mesh_score_{target_field}")

            hazard_mesh_layer = QgsProject.instance().mapLayersByName(
                f"mesh_score_{target_field}"
            )[0]

            graduate_layer(hazard_mesh_layer, target_field, breaks)

            self._display_only("mesh_score", target_field)
            self._display_only("seamless", target_field)

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def _set_classified_hazard_score(self):
        """
        update hazard_score field 't_{hazard}' in target layer (default mesh_score)
        with score defined in UI (TCG方式, standard deviation or custom)
        """

        if not self.main.mesh_score_layer_combobox.currentLayer():
            error_message = "対象HMGデータレイヤ(例：mesh_score)が足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        try:
            mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()

            # list of added fields
            rank_fields_added = self._calculate_ui_score(
                mesh_score_layer, self.main.custom_hmg_fieldname.text()
            )

            # add to each mesh_score_{hazard_name} layer
            for hazard_field in rank_fields_added:
                hazard_name = hazard_field.split("_")[1]

                # create if not exists
                if not QgsProject.instance().mapLayersByName(
                    f"mesh_score_{hazard_name}"
                ):
                    add_layer = mesh_score_layer.clone()
                    add_to_map(add_layer, f"mesh_score_{hazard_name}")

                hazard_mesh_layer = QgsProject.instance().mapLayersByName(
                    f"mesh_score_{hazard_name}"
                )[0]
                self._calculate_ui_score(
                    hazard_mesh_layer, self.main.custom_hmg_fieldname.text()
                )

            # message end
            message = "点数化が完了しました。\n計算した属性:\n"
            for rank_field in rank_fields_added:
                message += f"{rank_field}\n"
            if len(rank_fields_added) == 0:
                message += "なし"
            QMessageBox.information(None, "完了", message)

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def _calculate_ui_score(
        self, mesh_score_layer: QgsVectorLayer, custom_field_name: str
    ) -> list:
        # list of added fields
        rank_fields_added = []
        for hazard in constants.hazards_ui_names:
            # get mesh_score target field name
            if hazard == "custom":
                target_field = custom_field_name
            else:
                target_field = getattr(constants, f"field_{hazard}")

            if target_field in mesh_score_layer.fields().names():
                field_values = [
                    feature[target_field] for feature in mesh_score_layer.getFeatures()
                ]
                y_values = sorted(field_values)
            else:
                continue
            # get ranks from values
            rank_field = f"t_{target_field}"

            tcg_button = getattr(self.main, f"radiobutton_tcg_{hazard}")
            if tcg_button.isChecked():
                # get ranks from tcg method
                ranks = get_tcg_ranks(y_values)
            else:
                # get ranks for standard deviation or custom method as defined in UI
                ranks = self._get_ui_ranks(y_values, hazard)

            # add tcg rank field if not exists
            if rank_field not in mesh_score_layer.fields().names():
                mesh_score_layer.startEditing()
                mesh_score_layer.addAttribute(QgsField(rank_field, QVariant.Int))
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
                feature.setAttribute(rank_field, ranks[index])
                mesh_score_layer.updateFeature(feature)

            # Stop editing and save changes
            mesh_score_layer.commitChanges()

            rank_fields_added.append(rank_field)

        return rank_fields_added

    def _get_ui_ranks(self, values: list, hazard: str) -> list:
        """Return a list of rank associated to ui input values
        and percentages set
        input values :[0,10,255,3598,3699,8555]
        output ui_ranks : [0,0,1,2,3,4]
        """
        ui_ranks = []
        for value in values:
            for n in range(0, 11):
                percentage_box = getattr(self.main, f"classif_percent_{n}_{hazard}")
                percent_value = percentage_box.value()
                break_max = get_mesh_value_from_percentage(values, percent_value)

                if value == break_max and value > 0 and sum(ui_ranks) == 0:
                    print(value, break_max, 1)
                    ui_ranks.append(1)
                    break
                elif value <= break_max:
                    print(value, break_max, n)
                    ui_ranks.append(n)
                    break

        return ui_ranks
