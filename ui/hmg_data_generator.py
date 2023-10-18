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
from converter.seamless2hmg import seamless2hmg_kosui, seamless2hmg_jisuberi
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
        self.main.pushButton_processhmg.clicked.connect(self.process_hmg)

        # 縮尺コントローラー
        self.scale_list = [10000, 25000, 50000, 100000, 250000]
        # self.main.comboBox_scale.addItems(
        #     list(map(lambda x: f"1:{x}", self.scale_list))
        # )
        # self.main.comboBox_scale.currentTextChanged.connect(
        #     self._on_scale_widget_changed
        # )
        self.main.scale_widget.scaleChanged.connect(self._on_scale_widget_changed)
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

    def _on_scale_widget_changed(self):
        scale = self.main.scale_widget.scale()
        self.canvas.zoomScale(scale)

    def _on_map_scale_changed(self, scale):
        self.main.scale_widget.setScale(scale)
        # nearest_scale = min(self.scale_list, key=lambda x: abs(x - scale))
        # self.main.comboBox_scale.setCurrentText(f"1:{nearest_scale}")

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

        mesh_lyr.setName("mesh_score")
        QgsProject.instance().addMapLayer(mesh_lyr)
