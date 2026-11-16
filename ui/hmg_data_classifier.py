from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsMapLayerProxyModel,
    QgsField,
    QgsFeatureRequest,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
)

from qgis.utils import iface
from converter.mesh_score_classifier import (
    graduate_layer,
    get_mesh_value_from_percentage,
    get_color_from_range,
    classify_values_stdev,
    classify_values_tcg,
)

import constants
from utils import add_to_map, configure_hmg_layer_tree
from modules import pyqtgraph as pg
from scoring.qgis_layer import LayerScoringError, calculate_layer_scores
from scoring.classification import (
    classify_standard_deviation_ranks,
    classify_tcg_ranks,
)


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

        self.hzd_multiplier_initialized = False
        self._hide_unused_hazard_controls()
        self._add_game_score_controls()

        # stdev calculation flag to make calculate only once
        self.stdev_calculating = False

        # Custom method Sum surfaces as Default
        self.main.btn_custom_calc_sumsurf.setChecked(True)

        for hazard in constants.hazards_ui_names:
            # Connect graphs
            show_graph_button = getattr(self.main, f"classif_showgraph_{hazard}")
            show_graph_function = getattr(self, f"on_show_chart_clicked_{hazard}")
            show_graph_button.clicked.connect(show_graph_function)

            # ゲームの既定値は6ランク。1〜10の範囲で変更可能。
            on_number_changed_function = getattr(self, f"on_number_changed_{hazard}")
            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            nbmax_box.setRange(1, 10)
            nbmax_box.setValue(6)
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
            tcg_button.setChecked(True)

            # custom button
            custom_button = getattr(self.main, f"radiobutton_custom_{hazard}")
            custom_button.clicked.connect(on_number_changed_function)
            custom_button.hide()

    def _hide_unused_hazard_controls(self):
        """ゲームで使用しない旧分類項目を画面から隠す。"""

        for widget in self.main.findChildren(QWidget):
            object_name = widget.objectName()
            if any(
                object_name.endswith(f"_{hazard}")
                for hazard in constants.inactive_hazards_ui_names
            ):
                widget.hide()

        self.main.label_classif_title_kozui.setText("洪水")
        self.main.label_classif_title_sediments.setText("土砂災害")
        self.main.label_classif_title_slope.setText("傾斜度（警戒区域外）")

    def _find_layout_containing(self, layout, widget):
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is widget:
                return layout
            child_layout = item.layout()
            if child_layout:
                found = self._find_layout_containing(child_layout, widget)
                if found:
                    return found
        return None

    def _add_game_score_controls(self):
        """既存の実行ボタン行へ総合得点の最小限の設定を追加する。"""

        button_layout = self._find_layout_containing(
            self.main.scrollAreaWidgetContents.layout(),
            self.main.pushButton_classify,
        )
        if button_layout is None:
            return

        self.recalculation_target = QComboBox(self.main)
        self.recalculation_target.setObjectName("recalculation_target")
        self.recalculation_target.addItem("全災害（初回・一括）", "all")
        self.recalculation_target.addItem("洪水のみ", "kozui")
        self.recalculation_target.addItem("土砂災害のみ", "sediments")
        self.recalculation_target.addItem("傾斜度のみ", "slope")
        self.recalculation_target.addItem("津波のみ", "tsunami")

        self.hzd_target_maximum = QSpinBox(self.main)
        self.hzd_target_maximum.setObjectName("hzd_target_maximum")
        self.hzd_target_maximum.setRange(1, 999)
        self.hzd_target_maximum.setValue(15)

        self.hzd_multiplier = QDoubleSpinBox(self.main)
        self.hzd_multiplier.setObjectName("hzd_multiplier")
        self.hzd_multiplier.setRange(0.01, 100.0)
        self.hzd_multiplier.setDecimals(3)
        self.hzd_multiplier.setSingleStep(0.05)
        self.hzd_multiplier.setValue(1.0)

        self.recalculate_multiplier_button = QPushButton(
            "目標点から倍率を再計算", self.main
        )
        self.recalculate_multiplier_button.setObjectName(
            "pushButton_recalculate_multiplier"
        )
        self.recalculate_multiplier_button.clicked.connect(
            self._recalculate_hzd_multiplier
        )

        self.game_score_status = QLabel("未計算", self.main)
        self.game_score_status.setObjectName("label_game_score_status")

        button_index = button_layout.indexOf(self.main.pushButton_classify)
        button_layout.insertWidget(button_index, QLabel("再計算対象", self.main))
        button_layout.insertWidget(button_index + 1, self.recalculation_target)
        button_layout.insertWidget(button_index + 2, QLabel("目標最高点", self.main))
        button_layout.insertWidget(button_index + 3, self.hzd_target_maximum)
        button_layout.insertWidget(button_index + 4, QLabel("HZD倍率", self.main))
        button_layout.insertWidget(button_index + 5, self.hzd_multiplier)
        button_layout.insertWidget(
            button_index + 6, self.recalculate_multiplier_button
        )
        button_layout.insertWidget(button_index + 7, self.game_score_status)
        self.main.pushButton_classify.setText("点数を計算／再計算")

    def _update_game_score_status(self, result):
        self.hzd_multiplier.blockSignals(True)
        self.hzd_multiplier.setValue(result.hzd_multiplier)
        self.hzd_multiplier.blockSignals(False)
        self.hzd_multiplier_initialized = True

        status = (
            f"最大 A33: {result.maximum_a33} / "
            f"補正前: {result.maximum_base_hzd} / "
            f"HZD: {result.maximum_hzd}"
        )
        if result.sediment_slope_overlap_count:
            status += (
                " / 警告: 土砂と傾斜の重複 "
                f"{result.sediment_slope_overlap_count}件"
            )
            self.game_score_status.setStyleSheet("color: #b54708;")
        else:
            self.game_score_status.setStyleSheet("")
        self.game_score_status.setText(status)

    def _calculate_game_scores(self, mesh_score_layer, recalculate_multiplier=False):
        multiplier = None
        if self.hzd_multiplier_initialized and not recalculate_multiplier:
            multiplier = self.hzd_multiplier.value()
        result = calculate_layer_scores(
            mesh_score_layer,
            hzd_multiplier=multiplier,
            hzd_target_maximum=self.hzd_target_maximum.value(),
        )
        self._update_game_score_status(result)
        configure_hmg_layer_tree()
        return result

    def _recalculate_hzd_multiplier(self):
        mesh_score_layer = self.main.mesh_score_layer_combobox.currentLayer()
        if not mesh_score_layer:
            QMessageBox.information(
                None, "エラー", "点数を再計算するメッシュレイヤーを選択してください。"
            )
            return
        try:
            result = self._calculate_game_scores(
                mesh_score_layer, recalculate_multiplier=True
            )
        except LayerScoringError as error:
            QMessageBox.information(None, "エラー", str(error))
            return
        QMessageBox.information(
            None,
            "完了",
            "現在の点数分布からHZD倍率を再計算しました。\n"
            f"倍率: {result.hzd_multiplier:.3f}",
        )

    def on_number_changed_tornado(self):
        self._set_percentages("tornado")
        self.update_map_tornado()

    def on_number_changed_kozui(self):
        self._set_percentages("kozui")
        self.update_map_kozui()

    def on_number_changed_sediments(self):
        self._set_percentages("sediments")
        self.update_map_sediments()

    def on_number_changed_tsunami(self):
        self._set_percentages("tsunami")
        self.update_map_tsunami()

    def on_number_changed_jisuberi(self):
        self._set_percentages("jisuberi")
        self.update_map_jisuberi()

    def on_number_changed_saigai(self):
        self._set_percentages("saigai")
        self.update_map_saigai()

    def on_number_changed_surge(self):
        self._set_percentages("surge")
        self.update_map_surge()

    def on_number_changed_earthquake(self):
        self._set_percentages("earthquake")
        self.update_map_earthquake()

    def on_number_changed_slope(self):
        self._set_percentages("slope")
        self.update_map_slope()

    def on_number_changed_refuge(self):
        self._set_percentages("refuge")
        self.update_map_refuge()

    def on_number_changed_custom(self):
        self._set_percentages("custom")
        self.update_map_custom()

    def on_show_chart_clicked_tornado(self):
        self._set_map_and_chart("竜巻", "tornado", display_chart=True)

    def on_show_chart_clicked_kozui(self):
        self._set_map_and_chart("洪水", "kozui", display_chart=True)

    def on_show_chart_clicked_sediments(self):
        self._set_map_and_chart("土砂", "sediments", display_chart=True)

    def on_show_chart_clicked_tsunami(self):
        self._set_map_and_chart("津波", "tsunami", display_chart=True)

    def on_show_chart_clicked_jisuberi(self):
        self._set_map_and_chart("地すべり", "jisuberi", display_chart=True)

    def on_show_chart_clicked_saigai(self):
        self._set_map_and_chart("災害危険", "saigai", display_chart=True)

    def on_show_chart_clicked_surge(self):
        self._set_map_and_chart("高潮", "surge", display_chart=True)

    def on_show_chart_clicked_earthquake(self):
        self._set_map_and_chart("地震", "earthquake", display_chart=True)

    def on_show_chart_clicked_slope(self):
        self._set_map_and_chart("傾斜度", "slope", display_chart=True)

    def on_show_chart_clicked_refuge(self):
        self._set_map_and_chart("避難施設", "refuge", display_chart=True)

    def on_show_chart_clicked_custom(self):
        self._set_map_and_chart(
            self.main.custom_hmg_seamlessfilename.text(), "custom", display_chart=True
        )

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
                nbmax_box.setReadOnly(False)
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
            percentages_classes = classify_values_tcg(
                y_values, nbmax_box.value()
            )

            # update UI
            nbmax_box.setReadOnly(False)

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

    def update_map_tornado(self):
        self._set_map_and_chart("竜巻", "tornado")

    def update_map_kozui(self):
        self._set_map_and_chart("洪水", "kozui")

    def update_map_sediments(self):
        self._set_map_and_chart("土砂", "sediments")

    def update_map_tsunami(self):
        self._set_map_and_chart("津波", "tsunami")

    def update_map_jisuberi(self):
        self._set_map_and_chart("地すべり", "jisuberi")

    def update_map_saigai(self):
        self._set_map_and_chart("災害危険", "saigai")

    def update_map_surge(self):
        self._set_map_and_chart("高潮", "surge")

    def update_map_earthquake(self):
        self._set_map_and_chart("地震", "earthquake")

    def update_map_slope(self):
        self._set_map_and_chart("傾斜度", "slope")

    def update_map_refuge(self):
        self._set_map_and_chart("避難施設", "refuge")

    def update_map_custom(self):
        self._set_map_and_chart(self.main.custom_hmg_seamlessfilename.text(), "custom")

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

    def _set_map_and_chart(
        self, chart_title: str, hazard: str, display_chart=False
    ) -> None:
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

            if display_chart:
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

            # set classes for map and chart
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

                # graph : add break_max line as plot
                if display_chart:
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

            target = self.recalculation_target.currentData()
            hazards = (
                list(constants.hazards_ui_names)
                if target == "all"
                else [target]
            )
            risk_fields = [
                getattr(constants, f"field_{hazard}") for hazard in hazards
            ]
            missing_risk_fields = [
                field
                for field in risk_fields
                if field not in mesh_score_layer.fields().names()
            ]
            if missing_risk_fields:
                raise LayerScoringError(
                    "再計算に必要なリスク値フィールドがありません: "
                    + ", ".join(missing_risk_fields)
                )
            if target != "all":
                required_rank_fields = [
                    f"t_{getattr(constants, f'field_{hazard}')}"
                    for hazard in constants.hazards_ui_names
                ]
                missing_rank_fields = [
                    field
                    for field in required_rank_fields
                    if field not in mesh_score_layer.fields().names()
                ]
                if missing_rank_fields:
                    raise LayerScoringError(
                        "選択した災害だけを再計算する前に、"
                        "「全災害（初回・一括）」で初回点数化を実行してください。\n"
                        "不足フィールド: " + ", ".join(missing_rank_fields)
                    )

            # list of added fields
            rank_fields_added = self._calculate_ui_score(
                mesh_score_layer,
                self.main.custom_hmg_fieldname.text(),
                hazards,
            )

            try:
                game_result = self._calculate_game_scores(mesh_score_layer)
            except LayerScoringError as error:
                if target != "all":
                    raise LayerScoringError(
                        "選択した災害だけを再計算する前に、"
                        "「全災害（初回・一括）」で初回点数化を実行してください。\n"
                        f"詳細: {error}"
                    ) from error
                raise

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
                    hazard_mesh_layer,
                    self.main.custom_hmg_fieldname.text(),
                    hazards,
                )

                # label mesh_score_{hazard} with score
                label_settings = QgsPalLayerSettings()
                label_settings.fieldName = hazard_field
                label_settings.enabled = True

                # Set font properties
                text_format = QgsTextFormat()
                text_format.setFont(QFont("Arial Narrow", 8))
                text_format.setSize(8)
                label_settings.setFormat(text_format)

                # Apply label settings to the layer
                hazard_mesh_layer.setLabeling(
                    QgsVectorLayerSimpleLabeling(label_settings)
                )
                hazard_mesh_layer.setLabelsEnabled(True)
                hazard_mesh_layer.triggerRepaint()

            # message end
            target_label = self.recalculation_target.currentText()
            message = f"点数化が完了しました（{target_label}）。\n計算した属性:\n"
            for rank_field in rank_fields_added:
                message += f"{rank_field}\n"
            if len(rank_fields_added) == 0:
                message += "なし"
            message += (
                "\n\nゲーム用総合得点:"
                f"\n- HZD倍率: {game_result.hzd_multiplier:.3f}"
                f"\n- 最大HZD: {game_result.maximum_hzd}"
            )
            QMessageBox.information(None, "完了", message)

        except Exception as e:
            QMessageBox.information(
                None,
                "エラー",
                f"エラーが発生しました：\n{e}",
            )
            return

    def _calculate_ui_score(
        self,
        mesh_score_layer: QgsVectorLayer,
        custom_field_name: str,
        hazards=None,
    ) -> list:
        # list of added fields
        rank_fields_added = []
        target_hazards = hazards or constants.hazards_ui_names
        for hazard in target_hazards:
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

            stdev_button = getattr(self.main, f"radiobutton_stdev_{hazard}")
            tcg_button = getattr(self.main, f"radiobutton_tcg_{hazard}")
            nbmax_box = getattr(self.main, f"classif_nbmax_{hazard}")
            if stdev_button.isChecked():
                ranks = classify_standard_deviation_ranks(
                    y_values, nbmax_box.value()
                )
            elif tcg_button.isChecked():
                ranks = classify_tcg_ranks(y_values, nbmax_box.value())
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
