import os
import csv
import constants
import processing

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.PyQt import uic
from qgis.utils import iface

from maptool import POIMapTool


class HGMDataGenerator:
    def __init__(self, main: QDialog):
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # ラムダ式でもconnectできる
        self.main.pushButton_choosepnt.clicked.connect(
            self.activate_maptool_point
        )
        self.main.pushButton_mesh.clicked.connect(
            lambda: self.generate_mesh(self.main.lineEdit_x.text(), self.main.lineEdit_y.text())
        )
        self.main.pushButton_cancel.clicked.connect(lambda: self.main.close())

        # 縮尺コントローラー
        self.scale_list = [10000, 25000, 50000, 100000, 250000]
        self.main.comboBox_scale.addItems(list(map(lambda x: f"1:{x}", self.scale_list)))
        self.main.comboBox_scale.currentTextChanged.connect(self._on_combobox_scale_changed)
        self.canvas.scaleChanged.connect(self._on_map_scale_changed)

        # 都道府県リストを読み込む
        self.main.comboBox_pref.currentTextChanged.connect(self._on_pref_changed)
        self.pref_city_csv = os.path.join(os.path.dirname(__file__), constants.data_dir, "bnd_a_wm.csv")
        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            knames = list(dict.fromkeys([row['KNAME'] for row in reader]))
            for kname in knames:
                self.main.comboBox_pref.addItem(kname)

        self.main.comboBox_city.currentTextChanged.connect(self._on_city_changed)

    def _on_pref_changed(self, text):
        self.main.comboBox_city.clear()
        with open(self.pref_city_csv, "r") as f:
            reader = csv.DictReader(f)
            names = list(dict.fromkeys([row['NAME'] for row in reader if row['KNAME'] == text]))
            for name in names:
                self.main.comboBox_city.addItem(name)

    def _on_city_changed(self):
        try:
            with open(self.pref_city_csv, "r") as f:
                reader = csv.DictReader(f)
                bbox = [[row['x_min'], row["x_max"], row["y_min"], row["y_max"]] for row in reader if
                        row['KNAME'] == self.main.comboBox_pref.currentText() and row[
                            'NAME'] == self.main.comboBox_city.currentText()][0]

            self.canvas.setExtent(QgsRectangle(float(bbox[0]), float(bbox[2]), float(bbox[1]), float(bbox[3])))
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
        if self.radioButton_city.isChecked():
            with open(self.pref_city_csv, "r") as f:
                reader = csv.DictReader(f)
                bbox = [[row['x_min'], row["x_max"], row["y_min"], row["y_max"]] for row in reader if
                        row['KNAME'] == self.main.comboBox_pref.currentText() and row[
                            'NAME'] == self.main.comboBox_city.currentText()][0]

            grid_extent = f"{bbox[0]}, {bbox[1]},{bbox[2]},{bbox[3]} [EPSG:3857]"
            scale = iface.mapCanvas().scale()
            grid_map_size = 6 * scale / 100



        elif self.main.radioButton_point.isChecked():
            """中心点座標からメッシュを作成する"""
            center_x = float(center_x)
            center_y = float(center_y)
            scale = 25000
            grid_map_size = 6 * scale / 100

            nrows = 8
            ncolumns = 12
            grid_extent = f"{center_x - (grid_map_size * ncolumns / 2)}, {center_x + (grid_map_size * ncolumns / 2)},{center_y - (grid_map_size * nrows / 2)},{center_y + (grid_map_size * nrows / 2)} [EPSG:3857]"

        # output_path = r"C:/Users/kyokushinmyou/Documents/mesh.gpkg"
        output_layer = processing.run("native:creategrid",
                                      {'TYPE': 2, 'EXTENT': grid_extent, 'HSPACING': grid_map_size,
                                       'VSPACING': grid_map_size,
                                       'HOVERLAY': 0,
                                       'VOVERLAY': 0, 'CRS': QgsCoordinateReferenceSystem('EPSG:3857'),
                                       'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT})["OUTPUT"]

        QgsProject.instance().addMapLayer(output_layer)
        output_layer.setName(f"mesh_{self.main.comboBox_pref.currentText()}_{self.main.comboBox_city.currentText()}")
        output_layer.setOpacity(0.5)

        # ワクを作成
        # A1の紙のサイズ
        space = 6 * scale / 100

        mesh_extent = output_layer.extent()
        waku = QgsRectangle(mesh_extent.xMinimum() - space, mesh_extent.yMinimum() - space,
                            mesh_extent.xMaximum() + space, mesh_extent.yMaximum() + space)
        self.canvas.setExtent(waku)
        self.canvas.refresh()
