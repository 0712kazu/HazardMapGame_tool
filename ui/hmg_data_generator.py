import csv
import os

import processing
from PyQt5.QtWidgets import QDialog
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsProcessing,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.gui import QtCore
from qgis.utils import iface

import constants
from maptool import POIMapTool


class HGMDataGenerator:
    def __init__(self, main: QDialog):
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # ラムダ式でもconnectできる
        self.main.pushButton_choosepnt.clicked.connect(self.activate_maptool_point)
        self.main.pushButton_mesh.clicked.connect(
            lambda: self.generate_mesh(
                self.main.lineEdit_x.text(), self.main.lineEdit_y.text()
            )
        )
        self.main.pushButton_cancel.clicked.connect(lambda: self.main.close())

        # 縮尺コントローラー
        self.scale_list = [10000, 25000, 50000, 100000, 250000]
        self.main.comboBox_scale.addItems(
            list(map(lambda x: f"1:{x}", self.scale_list))
        )
        self.main.comboBox_scale.currentTextChanged.connect(
            self._on_combobox_scale_changed
        )
        self.canvas.scaleChanged.connect(self._on_map_scale_changed)

        # 都道府県リストを読み込む
        self.main.comboBox_pref.currentTextChanged.connect(self._on_pref_changed)
        self.pref_city_csv = os.path.join(
            os.path.dirname(__file__), constants.data_dir, "bnd_a_wm.csv"
        )
        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            knames = list(dict.fromkeys([row["KNAME"] for row in reader]))
            for kname in knames:
                self.main.comboBox_pref.addItem(kname)

        self.main.comboBox_city.currentTextChanged.connect(self._on_city_changed)

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
            with open(self.pref_city_csv, "r") as f:
                reader = csv.DictReader(f)
                bbox = [
                    [row["x_min"], row["x_max"], row["y_min"], row["y_max"]]
                    for row in reader
                    if row["KNAME"] == self.main.comboBox_pref.currentText()
                    and row["NAME"] == self.main.comboBox_city.currentText()
                ][0]

            self.canvas.setExtent(
                QgsRectangle(
                    float(bbox[0]), float(bbox[2]), float(bbox[1]), float(bbox[3])
                )
            )
            self.canvas.refresh()
        except IndexError:
            pass

    def _on_combobox_scale_changed(self, scale):
        self.canvas.zoomScale(int(scale.split(":")[1]))

    def _on_map_scale_changed(self, scale):
        nearest_scale = min(self.scale_list, key=lambda x: abs(x - scale))
        self.main.comboBox_scale.setCurrentText(f"1:{nearest_scale}")

    def activate_maptool_point(self):
        def show_xy(point):
            self.main.lineEdit_x.setText(str(point.x()))
            self.main.lineEdit_y.setText(str(point.y()))

        maptool = POIMapTool()
        maptool.clicked.connect(show_xy)
        iface.mapCanvas().setMapTool(maptool)

    def generate_mesh(self, center_x, center_y):
        if self.main.radioButton_city.isChecked():
            # 市区町村からメッシュを作成する
            self.generate_mesh_shikucyoson()

        elif self.main.radioButton_point.isChecked():
            # 中心点座標からメッシュを作成する
            self.generate_mesh_point(center_x, center_y)

    def generate_mesh_point(self, center_x, center_y):
        center_x = float(center_x)
        center_y = float(center_y)
        scale = 25000
        grid_map_size = 6 * scale / 100
        nrows = 8
        ncolumns = 12
        grid_extent_str = (
            f"{center_x - (grid_map_size * ncolumns / 2)},"
            f" {center_x + (grid_map_size * ncolumns / 2)},"
            f"{center_y - (grid_map_size * nrows / 2)},"
            f"{center_y + (grid_map_size * nrows / 2)} [EPSG:3857]"
        )

        mesh_layer = self.create_grid(grid_extent_str, grid_map_size)
        # ワクを作成
        # A1の紙のサイズ
        space = 6 * scale / 100
        mesh_extent = mesh_layer.extent()
        waku = QgsRectangle(
            mesh_extent.xMinimum() - space,
            mesh_extent.yMinimum() - space,
            mesh_extent.xMaximum() + space,
            mesh_extent.yMaximum() + space,
        )
        self.canvas.setExtent(waku)
        self.canvas.refresh()

    def create_grid(self, grid_extent_str, grid_map_size):
        output_layer = processing.run(
            "native:creategrid",
            {
                "TYPE": 2,
                "EXTENT": grid_extent_str,
                "HSPACING": grid_map_size,
                "VSPACING": grid_map_size,
                "HOVERLAY": 0,
                "VOVERLAY": 0,
                "CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
        )["OUTPUT"]
        QgsProject.instance().addMapLayer(output_layer)
        output_layer.setName(
            f"mesh_{self.main.comboBox_pref.currentText()}"
            f"_{self.main.comboBox_city.currentText()}"
        )
        output_layer.setOpacity(0.5)
        return output_layer

    def add_rect_as_a_layer(self, rect: QgsRectangle, layer_name: str):
        """QgsRectangleをレイヤーとして追加する"""
        rect_layer = QgsVectorLayer("Polygon?crs=epsg:3857", layer_name, "memory")
        provider = rect_layer.dataProvider()
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromRect(rect))
        provider.addFeatures([feature])
        QgsProject.instance().addMapLayer(rect_layer)
        rect_layer.setOpacity(0.5)

    def generate_mesh_shikucyoson(self):
        space = 200  # 余白
        mesh_size = 0.06  # メッシュのサイズ=6cm

        # A1の紙のサイズ
        long_side_a1 = 0.841
        short_side_a1 = 0.584

        # スケールの閾値
        scale_threshold = 25000

        # メッシュ数
        long_size_n = 12
        short_size_n = 8

        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            bbox = [
                [row["x_min"], row["x_max"], row["y_min"], row["y_max"]]
                for row in reader
                if row["KNAME"] == self.main.comboBox_pref.currentText()
                and row["NAME"] == self.main.comboBox_city.currentText()
            ][0]

        grid_x_min = float(bbox[0]) - space
        grid_x_max = float(bbox[1]) + space
        grid_y_min = float(bbox[2]) - space
        grid_y_max = float(bbox[3]) + space

        center_x = (grid_x_max - grid_x_min) / 2 + grid_x_min
        center_y = (grid_y_max - grid_y_min) / 2 + grid_y_min

        size_x = grid_x_max - grid_x_min
        size_y = grid_y_max - grid_y_min

        long_side = max([size_x, size_y])

        scale = long_side / (mesh_size * long_size_n)
        grid_map_size = long_side / long_size_n

        if scale < scale_threshold:
            # 縮尺が25000以下の場合,強制的に25000にする
            scale = scale_threshold
            grid_map_size = mesh_size * scale_threshold

            if size_x >= size_y:
                grid_x_min = center_x - mesh_size * scale_threshold * (long_size_n / 2)
                grid_x_max = center_x + mesh_size * scale_threshold * (long_size_n / 2)
                grid_y_min = center_y - mesh_size * scale_threshold * (short_size_n / 2)
                grid_y_max = center_y + mesh_size * scale_threshold * (short_size_n / 2)
            else:
                grid_x_min = center_x - mesh_size * scale_threshold * (short_size_n / 2)
                grid_x_max = center_x + mesh_size * scale_threshold * (short_size_n / 2)
                grid_y_min = center_y - mesh_size * scale_threshold * (long_size_n / 2)
                grid_y_max = center_y + mesh_size * scale_threshold * (long_size_n / 2)

        if size_x >= size_y:
            # 向き：横
            # 中心点からの距離をピッタリにすると、グリッドが一個多くできることがあるので、0.01mを引いている
            grid_extent_str = (
                f"{grid_x_min}, {grid_x_max},"
                f"{center_y - grid_map_size * (short_size_n / 2 - 0.01)},"
                f"{center_y + grid_map_size * (short_size_n / 2 - 0.01)} [EPSG:3857]"
            )
            waku_rec = QgsRectangle(
                center_x - long_side_a1 * scale / 2,
                center_y - short_side_a1 * scale / 2,
                center_x + long_side_a1 * scale / 2,
                center_y + short_side_a1 * scale / 2,
            )

        else:
            # 向き：縦
            grid_extent_str = (
                f"{center_x - grid_map_size * (short_size_n / 2 - 0.01)}, "
                f"{center_x + grid_map_size * (short_size_n / 2 - 0.01)},"
                f"{grid_y_min},{grid_y_max} [EPSG:3857]"
            )
            waku_rec = QgsRectangle(
                center_x - short_side_a1 * scale / 2,
                center_y - long_side_a1 * scale / 2,
                center_x + short_side_a1 * scale / 2,
                center_y + long_side_a1 * scale / 2,
            )

        self.add_rect_as_a_layer(
            waku_rec,
            f"waku_{self.main.comboBox_pref.currentText()}"
            f"_{self.main.comboBox_city.currentText()}",
        )
        self.canvas.setExtent(waku_rec)
        self.create_grid(grid_extent_str, grid_map_size)
