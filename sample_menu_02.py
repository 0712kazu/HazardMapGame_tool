import os

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.PyQt import uic
from qgis.utils import iface
import processing

from maptool import POIMapTool


class SampleMenu02(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(
            os.path.join(os.path.dirname(__file__), "sample_menu_02.ui"), self
        )

        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # ラムダ式でもconnectできる
        self.ui.pushButton_choosepnt.clicked.connect(
            self.activate_maptool_point
        )
        self.ui.pushButton_mesh.clicked.connect(
            lambda: self.generate_mesh(self.ui.lineEdit_x.text(), self.ui.lineEdit_y.text())
        )
        self.ui.pushButton_cancel.clicked.connect(lambda: self.close())

    def activate_maptool_point(self):
        def show_xy(point):
            self.ui.lineEdit_x.setText(str(point.x()))
            self.ui.lineEdit_y.setText(str(point.y()))

        maptool = POIMapTool()
        maptool.clicked.connect(show_xy)
        iface.mapCanvas().setMapTool(maptool)

    def generate_mesh(self, center_x, center_y):
        """中心点座標からメッシュを作成する"""
        center_x = float(center_x)
        center_y = float(center_y)

        output_path = r"C:/Users/kyokushinmyou/Documents/mesh.gpkg"

        # grid configuration for A1
        nrows = 10
        ncolumns = 16
        grid_cm_size = 6
        map_m_per_cm_size = 250  # scale 1:25000 / 1cm = 250m

        grid_map_size = grid_cm_size * map_m_per_cm_size

        grid_extent = f"{center_x - (grid_map_size * ncolumns / 2)}, {center_x + (grid_map_size * ncolumns / 2)},{center_y - (grid_map_size * nrows / 2)},{center_y + (grid_map_size * nrows / 2)} [EPSG:3857]"

        processing.run("native:creategrid",
                       {'TYPE': 2, 'EXTENT': grid_extent, 'HSPACING': 1500, 'VSPACING': 1500, 'HOVERLAY': 0,
                        'VOVERLAY': 0, 'CRS': QgsCoordinateReferenceSystem('EPSG:3857'), 'OUTPUT': output_path})

        layer = QgsVectorLayer(output_path, "mesh", 'ogr')
        layer.setOpacity(0.5)
        QgsProject.instance().addMapLayer(layer)
