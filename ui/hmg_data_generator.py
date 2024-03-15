import processing
import csv
import os

from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsRectangle, QgsVectorLayer, QgsPointXY
from qgis.gui import QtCore
from qgis.utils import iface

import constants

from utils import add_to_map
from converter.seamless2hmg import (
    seamless2hmg_kosui,
    seamless2hmg_jisuberi,
    seamless2hmg_saigai,
    seamless2hmg_tornado,
    seamless2hmg_sediments,
    seamless2hmg_tsunami,
    seamless2hmg_surge,
    seamless2hmg_earthquake,
    seamless2hmg_slope,
    seamless2hmg_refuge,
    seamless2hmg_custom,
    seamless2hmg_landuse,
)
from converter.mesh_maker import (
    generate_mesh_city,
    generate_mesh_point,
    exclude_offshore_mesh,
    set_mesh_id,
)

from converter.mesh_score_classifier import calculate_tcg_score

from utils import set_map_canvas_to_webmercator
from maptool import POIMapTool


class HMGDataGenerator:
    def __init__(self, main: QDialog):
        self.main = main
        self.canvas = iface.mapCanvas()

        # set map to webmercator
        set_map_canvas_to_webmercator()

        # ラムダ式でもconnectできる
        self.main.pushButton_choosepnt.clicked.connect(self.activate_maptool_point)
        self.main.pushButton_mesh.clicked.connect(self.generate_mesh)
        self.main.pushButton_cancel_2.clicked.connect(lambda: self.main.close())
        self.main.pushButton_processhmg.clicked.connect(self.process_hmg)

        # 都道府県リストを読み込む
        self.main.comboBox_pref.currentTextChanged.connect(self._on_pref_changed)

        # Take csv file in data folder as default, and seamless data if provided
        self._set_shikuchoson_csv_data()
        self.main.FileWidgetSeamlessDir.fileChanged.connect(
            self._set_shikuchoson_csv_data
        )

        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            knames = list(dict.fromkeys([row["KNAME"] for row in reader]))
            for kname in knames:
                self.main.comboBox_pref.addItem(kname)

        self.main.comboBox_city.currentTextChanged.connect(self._on_city_changed)

        # Filter pref cities by text
        self.main.filter_pref.textChanged.connect(self._on_pref_filter_changed)
        self.main.filter_city.textChanged.connect(self._on_city_filter_changed)

        # initialize a1 scale
        self._on_city_changed()
        self.main.a1_scale_widget.setScale(25000)

        # set log file
        self._set_log_csv_data()
        self.main.FileWidget_log.fileChanged.connect(self._set_log_csv_data)
        self.main.comboBox_meshprodlog.currentTextChanged.connect(self._on_log_changed)
        self.main.pushButton_savelog.clicked.connect(self.save_log)

        # mesh size
        self.main.nb_mesh1.setRange(1, 12)
        self.main.nb_mesh1.setValue(12)
        self.main.nb_mesh2.setRange(1, 8)
        self.main.nb_mesh2.setValue(8)

        # default inland value
        self.main.spin_inland_percentage.setValue(10)

    def _set_log_csv_data(self):
        # Take csv file in data folder as default, and CSV log data if provided
        if self.main.FileWidget_log.filePath():
            self.log_csv = self.main.FileWidget_log.filePath()
        else:
            self.log_csv = os.path.join(
                os.path.dirname(__file__), constants.data_dir, "mesh_production_log.csv"
            )

        self.main.comboBox_meshprodlog.clear()
        self.main.comboBox_meshprodlog.addItem("Select...")
        with open(self.log_csv, "r") as f:
            reader = csv.DictReader(f)
            lognames = list(dict.fromkeys([row["title"] for row in reader]))
            for logname in lognames:
                self.main.comboBox_meshprodlog.addItem(logname)

    def _on_log_changed(self):
        # set map to webmercator
        set_map_canvas_to_webmercator()

        with open(self.log_csv, "r") as f:
            reader = csv.DictReader(f)
            logs = [
                row
                for row in reader
                if row["title"] == self.main.comboBox_meshprodlog.currentText()
            ]

            for log in logs:
                if log["type"] == "city":
                    self.main.filter_pref.setText("")
                    self.main.filter_city.setText("")
                    self.main.radioButton_city.setChecked(True)
                    self.main.comboBox_pref.setCurrentText(log["pref"])
                    self.main.comboBox_city.setCurrentText(log["city"])
                    # center map canvas to city
                    self._on_city_changed()
                if log["type"] == "point":
                    self.main.radioButton_point.setChecked(True)
                    self.main.comboBox_orientation.setCurrentText(log["orientation"])
                    self.main.lineEdit_x.setText(log["center_x"])
                    self.main.lineEdit_y.setText(log["center_y"])
                    self.main.nb_mesh1.setValue(int(log["mesh_size_long"]))
                    self.main.nb_mesh2.setValue(int(log["mesh_size_short"]))
                    self.main.a1_scale_widget.setScale(
                        float(log["scale"].split(":")[1])
                    )
                    # center map canvas  to centroid
                    iface.mapCanvas().zoomScale(120000)
                    iface.mapCanvas().setCenter(
                        QgsPointXY(float(log["center_x"]), float(log["center_y"]))
                    )

    def save_log(self):
        # checkpoint 1: title should not be empty
        if self.main.lineEdit_title.text() == "":
            QMessageBox.information(None, "エラー", "ログ名を記入してください。")
            return

        with open(self.log_csv, "r") as f:
            # checkpoint 2 : title should not already exists
            reader = csv.DictReader(f)
            titles = list(dict.fromkeys([row["title"] for row in reader]))
            if self.main.lineEdit_title.text() in titles:
                QMessageBox.information(
                    None,
                    "エラー",
                    f"「{self.main.lineEdit_title.text()}」のログ名が既に保存されています。",
                )
                return

        # 2 checkpoints passed, save log
        if self.main.radioButton_city.isChecked():
            log = {
                "title": self.main.lineEdit_title.text(),
                "paper_size": "A1",
                "type": "city",
                "pref": self.main.comboBox_pref.currentText(),
                "city": self.main.comboBox_city.currentText(),
                "scale": self.main.a1_scale_label.text(),
                "orientation": "",
                "center_x": "",
                "center_y": "",
                "mesh_size_long": 12,
                "mesh_size_short": 8,
            }

        if self.main.radioButton_point.isChecked():
            # checkpoint 3 : center point should be set
            if self.main.lineEdit_x.text() == "" or self.main.lineEdit_y.text() == "":
                QMessageBox.information(
                    None,
                    "エラー",
                    "中心点が指定していません。",
                )
                return
            log = {
                "title": self.main.lineEdit_title.text(),
                "paper_size": "A1",
                "type": "point",
                "pref": "",
                "city": "",
                "scale": f"1:{round(self.main.a1_scale_widget.scale())}",
                "orientation": self.main.comboBox_orientation.currentText(),
                "center_x": self.main.lineEdit_x.text(),
                "center_y": self.main.lineEdit_y.text(),
                "mesh_size_long": self.main.nb_mesh1.value(),
                "mesh_size_short": self.main.nb_mesh2.value(),
            }
        # save in csv file
        with open(self.log_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=log.keys())
            writer.writerow(log)

        # update log list
        self._set_log_csv_data()

        QMessageBox.information(
            None,
            "Information",
            f"「{self.main.lineEdit_title.text()}」ログが保存しました。",
        )

    def _set_shikuchoson_csv_data(self):
        # Take csv file in data folder as default, and seamless data if provided
        seamless_shikuchoson = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_CITIES
        )
        if os.path.exists(seamless_shikuchoson):
            self.pref_city_csv = seamless_shikuchoson
        else:
            self.pref_city_csv = os.path.join(
                os.path.dirname(__file__),
                constants.data_dir,
                constants.SEAMLESS_FILE_CITIES,
            )

        # re-initialize pref-city list
        self.main.comboBox_pref.clear()
        self.main.filter_pref.clear()
        self.main.filter_city.clear()
        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            knames = list(dict.fromkeys([row["KNAME"] for row in reader]))
            for kname in knames:
                self.main.comboBox_pref.addItem(kname)

    def _on_pref_filter_changed(self):
        text = self.main.filter_pref.text()
        self.main.comboBox_pref.clear()

        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            names = list(
                dict.fromkeys(
                    [
                        row["KNAME"]
                        for row in reader
                        if row["KNAME"].startswith(text)
                        or row["KKANA"].startswith(text)
                    ]
                )
            )
            for name in names:
                self.main.comboBox_pref.addItem(name)
        self.main.filter_city.clear()

    def _on_city_filter_changed(self):
        text = self.main.filter_city.text()
        self.main.comboBox_city.clear()

        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            names = list(
                dict.fromkeys(
                    [
                        row["NAME"]
                        for row in reader
                        if row["KNAME"] == self.main.comboBox_pref.currentText()
                        if row["NAME"].startswith(text) or row["KANA"].startswith(text)
                    ]
                )
            )
            for name in names:
                self.main.comboBox_city.addItem(name)

    def _on_pref_changed(self, text):
        self.main.comboBox_city.clear()
        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            names = list(
                dict.fromkeys([row["NAME"] for row in reader if row["KNAME"] == text])
            )
            for name in names:
                self.main.comboBox_city.addItem(name)

    def _on_city_changed(self):
        try:
            # get city bbox
            with open(self.pref_city_csv, "r") as f:
                reader = csv.DictReader(f)
                bbox = [
                    [row["x_min"], row["x_max"], row["y_min"], row["y_max"]]
                    for row in reader
                    if row["KNAME"] == self.main.comboBox_pref.currentText()
                    and row["NAME"] == self.main.comboBox_city.currentText()
                ][0]

            # set map canvas to city extent
            self.canvas.setExtent(
                QgsRectangle(
                    float(bbox[0]), float(bbox[2]), float(bbox[1]), float(bbox[3])
                )
            )
            self.canvas.refresh()

            # calculate A1 scale
            scale = self._get_a1_scale_from_city_bbox(bbox)

            # スケールの閾値
            scale_threshold = 25000

            display_scale = f"1:{round(scale)}"
            if scale < scale_threshold:
                # 縮尺分母が25000以下の場合（例：22000）,強制的に25000にする
                display_scale = f"1:{round(scale)} → 1:25000"

            self.main.a1_scale_label.setText(display_scale)

        except IndexError:
            pass

    def _get_a1_scale_from_city_bbox(self, bbox: list) -> float:
        space = 200  # 余白
        mesh_size = 0.06  # メッシュのサイズin A1 paper=6cm

        # メッシュ数
        long_size_n = 12

        grid_x_min = float(bbox[0]) - space
        grid_x_max = float(bbox[1]) + space
        grid_y_min = float(bbox[2]) - space
        grid_y_max = float(bbox[3]) + space

        size_x = grid_x_max - grid_x_min
        size_y = grid_y_max - grid_y_min

        long_side = max([size_x, size_y])

        scale = long_side / (mesh_size * long_size_n)

        return scale

    def activate_maptool_point(self):
        # set map to webmercator
        set_map_canvas_to_webmercator()

        self.main.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        def show_xy(point):
            self.main.lineEdit_x.setText(str(point.x()))
            self.main.lineEdit_y.setText(str(point.y()))
            self.main.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            self.main.show()

        maptool = POIMapTool()
        maptool.clicked.connect(show_xy)
        iface.mapCanvas().setMapTool(maptool)

    def generate_mesh(self):
        # set map to webmercator
        set_map_canvas_to_webmercator()

        if self.main.radioButton_city.isChecked():
            # 市区町村からメッシュを作成する
            mesh_lyr = generate_mesh_city(
                self.main.comboBox_pref.currentText(),
                self.main.comboBox_city.currentText(),
                self.pref_city_csv,
            )

        elif self.main.radioButton_point.isChecked():
            if self.main.lineEdit_x.text() == "" or self.main.lineEdit_y.text() == "":
                QMessageBox.information(
                    None,
                    "エラー",
                    "中心点が指定していません。",
                )
                return
            # 中心点座標からメッシュを作成する
            mesh_lyr = generate_mesh_point(
                float(self.main.lineEdit_x.text()),
                float(self.main.lineEdit_y.text()),
                self.main.nb_mesh1.value(),
                self.main.nb_mesh2.value(),
                self.main.comboBox_orientation.currentText(),
                self.main.a1_scale_widget.scale(),
            )

        # exclude offshore mesh (more than 90% of water)
        landuse_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_LANDUSE
        )
        if os.path.exists(landuse_path):
            landuse_lyr = QgsVectorLayer(
                landuse_path,
                "landuse_merged",
                "ogr",
            )
            mesh_lyr = exclude_offshore_mesh(
                mesh_lyr, landuse_lyr, self.main.spin_inland_percentage.value()
            )
        else:
            message = f"対象シムレスフォルダーに{constants.SEAMLESS_FILE_LANDUSE}を見つかりませんでした。\n"
            message += "マスに陸域率を100%に指定します。"
            QMessageBox.information(None, "お知らせ", message)
            mesh_lyr = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": mesh_lyr,
                    "FIELD_NAME": "land_rate",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 0,
                    "FIELD_PRECISION": 0,
                    "FORMULA": "1",
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            )["OUTPUT"]

        # set mesh_id with left to right then up to bottom order
        set_mesh_id(mesh_lyr)

        add_to_map(mesh_lyr, "mesh")

        QMessageBox.information(None, "完了", "メッシュの作成が完了しました。")

    def process_hmg(self):
        # error handling
        if not self.main.FileWidgetSeamlessDir.filePath():
            error_message = "エラーが発生しました。\n\n"
            error_message += "シームレスフォルダーが設定していません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        if not QgsProject.instance().mapLayersByName("waku"):
            error_message = "エラーが発生しました。\n\n"
            error_message += "「waku」レイヤがありません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        if not QgsProject.instance().mapLayersByName("mesh"):
            error_message = "エラーが発生しました。\n\n"
            error_message += "「mesh」レイヤがありません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        # list of hazard processed
        hmg_processed = []

        waku_lyr = QgsProject.instance().mapLayersByName("waku")[0]
        mesh_lyr = QgsProject.instance().mapLayersByName("mesh")[0]

        # 土地利用
        # clip data seamless data only
        landuse_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_LANDUSE
        )
        if os.path.exists(landuse_path):
            landuse_lyr = QgsVectorLayer(
                landuse_path,
                "landuse_merged",
                "ogr",
            )
            if landuse_lyr:
                seamless2hmg_landuse(landuse_lyr, waku_lyr)

        # 竜巻
        tornado_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_TORNADO
        )
        if os.path.exists(tornado_path):
            tornado_lyr = QgsVectorLayer(
                tornado_path,
                "tornado_merged",
                "ogr",
            )
            if tornado_lyr:
                mesh_lyr = seamless2hmg_tornado(tornado_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_tornado)

        # 洪水
        kouzui_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_FLOOD
        )
        if os.path.exists(kouzui_path):
            kouzui_lyr = QgsVectorLayer(
                kouzui_path,
                "kouzui_merged",
                "ogr",
            )
            mesh_lyr = seamless2hmg_kosui(kouzui_lyr, waku_lyr, mesh_lyr, iface)
            hmg_processed.append(constants.field_kozui)

        # 土砂
        sediments_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_SEDIMENTS,
        )
        if os.path.exists(sediments_path):
            sediments_lyr = QgsVectorLayer(
                sediments_path,
                "sediments_merged",
                "ogr",
            )
            if sediments_lyr:
                mesh_lyr = seamless2hmg_sediments(sediments_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_sediments)

        # 津波
        tsunami_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_TSUNAMI,
        )
        if os.path.exists(tsunami_path):
            tsunami_lyr = QgsVectorLayer(
                tsunami_path,
                "tsunami_merged",
                "ogr",
            )
            if tsunami_lyr:
                mesh_lyr = seamless2hmg_tsunami(tsunami_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_tsunami)

        # 地すべり
        jisuberi_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_LANDSLIP
        )
        if os.path.exists(jisuberi_path):
            jisuberi_lyr = QgsVectorLayer(
                jisuberi_path,
                "jisuberi_merged",
                "ogr",
            )
            if jisuberi_lyr:
                mesh_lyr = seamless2hmg_jisuberi(jisuberi_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_jisuberi)

        # 災害危険
        saigai_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), constants.SEAMLESS_FILE_DISASTER
        )
        if os.path.exists(saigai_path):
            saigai_lyr = QgsVectorLayer(
                saigai_path,
                "saigai_merged",
                "ogr",
            )
            if saigai_lyr:
                mesh_lyr = seamless2hmg_saigai(saigai_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_saigai)

        # 高潮
        surge_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_SURGE,
        )
        if os.path.exists(surge_path):
            surge_lyr = QgsVectorLayer(
                surge_path,
                "surge_merged",
                "ogr",
            )
            if surge_lyr:
                mesh_lyr = seamless2hmg_surge(surge_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_surge)

        # 地震
        earthquake_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_EARTHQUAKE,
        )
        if os.path.exists(earthquake_path):
            earthquake_lyr = QgsVectorLayer(
                earthquake_path,
                "earthquake_merged",
                "ogr",
            )
            if earthquake_lyr:
                mesh_lyr = seamless2hmg_earthquake(earthquake_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_earthquake)

        # 傾斜度
        slope_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_SLOPE,
        )
        if os.path.exists(slope_path):
            slope_lyr = QgsVectorLayer(
                slope_path,
                "slope_merged",
                "ogr",
            )
            if slope_lyr:
                mesh_lyr = seamless2hmg_slope(slope_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_slope)

        # 避難施設
        refuge_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            constants.SEAMLESS_FILE_REFUGE,
        )
        if os.path.exists(refuge_path):
            refuge_lyr = QgsVectorLayer(
                refuge_path,
                "refuge_merged",
                "ogr",
            )
            if refuge_lyr:
                mesh_lyr = seamless2hmg_refuge(refuge_lyr, mesh_lyr, waku_lyr)
                hmg_processed.append(constants.field_refuge)

        # 追加災害
        custom_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(),
            self.main.custom_hmg_seamlessfilename.text() + ".gpkg",
        )
        print(custom_path)
        if os.path.exists(custom_path):
            custom_lyr = QgsVectorLayer(
                custom_path,
                "hazard_custom_merged",
                "ogr",
            )
            custom_field = self.main.custom_hmg_fieldname.text()
            if custom_lyr and custom_field != "":
                # checked calculation method
                if self.main.btn_custom_calc_sumsurf.isChecked():
                    calc_method = "sum_surfaces"
                if self.main.btn_custom_calc_sumsurfvalue.isChecked():
                    calc_method = "sum_surfaces_values"
                if self.main.btn_custom_calc_centroidmean.isChecked():
                    calc_method = "centroid_value_mean"
                if self.main.btn_custom_calc_countpoints.isChecked():
                    calc_method = "count_points"

                mesh_lyr = seamless2hmg_custom(
                    custom_lyr,
                    mesh_lyr,
                    waku_lyr,
                    custom_field,
                    calc_method,
                    self.main.custom_seamless_fieldname.text(),
                    self.main.custom_inland_adjust_checkbox.isChecked(),
                )
                hmg_processed.append(custom_field)
                # change name of classification class
                self.main.label_classif_title_custom.setText(
                    self.main.custom_hmg_seamlessfilename.text()
                )
            elif custom_lyr and custom_field == "":
                message = "追加災害の属性名が記入されてません。"
                QMessageBox.information(None, "お知らせ", message)
                return

        # if no seamless data , message it
        if len(hmg_processed) == 0:
            message = "Seamless dataがありませんでした。"
            QMessageBox.information(None, "完了", message)
            return

        # Calculate TCG score
        calculate_tcg_score(mesh_lyr, self.main.custom_hmg_fieldname.text())

        # Add hazard layers to map
        for hazard in hmg_processed:
            hazard_lyr = mesh_lyr.clone()
            add_to_map(hazard_lyr, f"mesh_score_{hazard}")

        # Add final mesh score (all) layer to map
        add_to_map(mesh_lyr, "mesh_score")

        # set for HMG classifier
        score_layer = QgsProject.instance().mapLayersByName("mesh_score")[0]
        if score_layer:
            self.main.mesh_score_layer_combobox.setLayer(score_layer)

        # message end
        message = "HMGデータの作成が完了しました。\n計算した属性:\n"
        for hazard_processed in hmg_processed:
            message += f"{hazard_processed}\n"
        QMessageBox.information(None, "完了", message)
