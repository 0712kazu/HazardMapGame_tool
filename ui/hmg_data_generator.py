import csv
import os

from PyQt5.QtWidgets import QDialog
from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.gui import QtCore
from qgis.utils import iface

import constants
from converter.seamless2hmg import (
    seamless2hmg_kosui,
    seamless2hmg_jisuberi,
    seamless2hmg_saigai,
)
from converter.mesh_maker import (
    generate_mesh_city,
    generate_mesh_point,
    exclude_offshore_mesh,
)
from maptool import POIMapTool


class HGMDataGenerator:
    def __init__(self, main: QDialog):
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # ラムダ式でもconnectできる
        self.main.pushButton_choosepnt.clicked.connect(self.activate_maptool_point)
        self.main.pushButton_mesh.clicked.connect(self.generate_mesh)
        self.main.pushButton_cancel.clicked.connect(lambda: self.main.close())
        self.main.pushButton_cancel_2.clicked.connect(lambda: self.main.close())
        self.main.pushButton_processhmg.clicked.connect(self.process_hmg)

        # 縮尺コントローラー
        # self.scale_list = [10000, 25000, 50000, 100000, 250000]
        # self.main.scale_widget.scaleChanged.connect(self._on_scale_widget_changed)
        # self.canvas.scaleChanged.connect(self._on_map_scale_changed)

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

        # mesh size
        self.main.nb_mesh1.setRange(1, 12)
        self.main.nb_mesh1.setValue(12)
        self.main.nb_mesh2.setRange(1, 8)
        self.main.nb_mesh2.setValue(8)

    def _set_shikuchoson_csv_data(self):
        # Take csv file in data folder as default, and seamless data if provided
        seamless_shikuchoson = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), "shikuchoson.csv"
        )
        if os.path.exists(seamless_shikuchoson):
            self.pref_city_csv = seamless_shikuchoson
        else:
            self.pref_city_csv = os.path.join(
                os.path.dirname(__file__), constants.data_dir, "shikuchoson.csv"
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

    # def _on_scale_widget_changed(self):
    #     scale = self.main.scale_widget.scale()
    #     self.canvas.zoomScale(scale)

    # def _on_map_scale_changed(self, scale):
    #     self.main.scale_widget.setScale(scale)

    def activate_maptool_point(self):
        def show_xy(point):
            self.main.lineEdit_x.setText(str(point.x()))
            self.main.lineEdit_y.setText(str(point.y()))

        maptool = POIMapTool()
        maptool.clicked.connect(show_xy)
        iface.mapCanvas().setMapTool(maptool)

    def generate_mesh(self):
        if self.main.radioButton_city.isChecked():
            # 市区町村からメッシュを作成する
            mesh_lyr = generate_mesh_city(
                self.main.comboBox_pref.currentText(),
                self.main.comboBox_city.currentText(),
                self.pref_city_csv,
            )

        elif self.main.radioButton_point.isChecked():
            # 中心点座標からメッシュを作成する
            mesh_lyr = generate_mesh_point(
                float(self.main.lineEdit_x.text()),
                float(self.main.lineEdit_y.text()),
                self.main.nb_mesh1.value(),
                self.main.nb_mesh2.value(),
                self.main.comboBox_orientation.currentText(),
            )

        # exclude offshore mesh (more than 90% of water)
        landuse_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), "tochiriyou_merged.gpkg"
        )
        if os.path.exists(landuse_path):
            landuse_lyr = QgsVectorLayer(
                landuse_path,
                "landuse_merged",
                "ogr",
            )
            mesh_lyr = exclude_offshore_mesh(mesh_lyr, landuse_lyr)

        QgsProject.instance().addMapLayer(mesh_lyr)
        mesh_lyr.setName("mesh")
        mesh_lyr.setOpacity(0.5)

    def process_hmg(self):
        waku_lyr = QgsProject.instance().mapLayersByName("waku")[0]
        mesh_lyr = QgsProject.instance().mapLayersByName("mesh")[0]

        kouzui_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), "kouzui_merged.gpkg"
        )
        if os.path.exists(kouzui_path):
            kouzui_lyr = QgsVectorLayer(
                kouzui_path,
                "kouzui_merged",
                "ogr",
            )
            mesh_lyr = seamless2hmg_kosui(kouzui_lyr, waku_lyr, mesh_lyr, iface)

        jisuberi_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), "jisuberi_merged.gpkg"
        )
        if os.path.exists(jisuberi_path):
            jisuberi_lyr = QgsVectorLayer(
                jisuberi_path,
                "jisuberi_merged",
                "ogr",
            )
            if jisuberi_lyr:
                mesh_lyr = seamless2hmg_jisuberi(jisuberi_lyr, mesh_lyr)

        saigai_path = os.path.join(
            self.main.FileWidgetSeamlessDir.filePath(), "saigai_merged.gpkg"
        )
        if os.path.exists(saigai_path):
            saigai_lyr = QgsVectorLayer(
                saigai_path,
                "saigai_merged",
                "ogr",
            )
            if saigai_lyr:
                mesh_lyr = seamless2hmg_saigai(saigai_lyr, mesh_lyr)

        mesh_lyr.setName("mesh_score")
        QgsProject.instance().addMapLayer(mesh_lyr)
