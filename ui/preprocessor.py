import os
import glob
import subprocess
import shutil
import processing

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.PyQt import uic
from qgis.utils import iface

from constants import (
    INPUT_DIR_KOZUI,
    INPUT_DIR_TOCHIRIYOU,
    INPUT_DIR_ZISUBERI,
    OUTPUT_DIR,
)
from ui.utils import unpack_zips_from_dir, get_shapefiles_from_dir


class Preprocessor:
    def __init__(self, main: QDialog):
        self.main = main

        self.main.pushButton_run.clicked.connect(self.run)
        self.main.pushButton_cancel.clicked.connect(self.main.close)

        self.main.pushButton_select_dir.clicked.connect(
            self.load_elements_files_from_dir
        )

    def load_elements_files_from_dir(self):
        """
        指定されたフォルダから複数のファイルを探し見つけたらFileWidgetに反映する
        """
        selected_dir = QFileDialog.getExistingDirectory(self.main, "フォルダを選択")

        for folder_name, filewidget in (
            (INPUT_DIR_KOZUI, self.main.QgsFileWidget_kozui),
            (INPUT_DIR_TOCHIRIYOU, self.main.QgsFileWidget_tochiriyou),
            (INPUT_DIR_ZISUBERI, self.main.QgsFileWidget_zisuberi),
            (OUTPUT_DIR, self.main.FileWidgetSeamlessDir),
        ):
            folders = glob.glob(
                os.path.join(selected_dir, folder_name), recursive=False
            )

            # ファイルが見つかったならウィジェットに反映する
            if len(folders) > 0:
                filewidget.setFilePath(folders[0])

    def run(self):
        if not self.main.FileWidgetSeamlessDir.filePath():
            error_message = "シームレスフォルダーが設定していません。"
            QMessageBox.information(None, "エラー", f"エラーが発生しました。\n\n{error_message}")
            return
        if self.main.QgsFileWidget_tochiriyou.filePath():
            self.preprocess_tochiriyou(
                self.main.QgsFileWidget_tochiriyou.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )
        if self.main.QgsFileWidget_kozui.filePath():
            self.preprocess_kozui(
                self.main.QgsFileWidget_kozui.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

    def preprocess_tochiriyou(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)

        cmd = f"ogr2ogr -lco ENCODING=cp932 -oo ENCODING=cp932 -f GPKG {os.path.join(output_directory, 'tochiriyou_merged.gpkg')} {shapefiles[0]}"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        for shp in shapefiles[1:]:
            cmd = f"ogr2ogr -lco ENCODING=cp932 -oo ENCODING=cp932 -f GPKG -append -update {os.path.join(output_directory, 'tochiriyou_merged.gpkg')} {shp}"
            subprocess.run(
                cmd,
                shell=True,
                check=True,
            )
        shutil.rmtree(extracted_dir)

    def preprocess_kozui(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)

        # merge all shapefiles in one
        merged_shapefiles = processing.run(
            "native:mergevectorlayers",
            {
                "LAYERS": shapefiles,
                "CRS": None,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

        # fix geometries
        kouzui_cleaned = processing.run(
            "native:fixgeometries",
            {
                "INPUT": merged_shapefiles,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

        # Depth calculation
        # TO DO: Consolidate fields in input shp and update formula
        processing.run(
            "native:fieldcalculator",
            {
                "INPUT": kouzui_cleaned,
                "FIELD_NAME": "depth",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 0,
                "FIELD_PRECISION": 0,
                "FORMULA": 'CASE\r\nWHEN "A31_001" = 11\r\nTHEN 0.2\r\nWHEN "A31_001" = 12\r\nTHEN 0.7\r\nWHEN "A31_001" = 13\r\nTHEN 1.4\r\nWHEN "A31_001" = 14\r\nTHEN 3\r\nWHEN "A31_001" = 15\r\nTHEN 7\r\nWHEN "A31_001" = 21\r\nTHEN 0.2\r\nWHEN "A31_001" = 22\r\nTHEN 0.7\r\nWHEN "A31_001" = 23\r\nTHEN 1.4\r\nWHEN "A31_001" = 24\r\nTHEN 2.4\r\nWHEN "A31_001" = 25\r\nTHEN 3.4\r\nWHEN "A31_001" = 26\r\nTHEN 4.4\r\nWHEN "A31_001" = 27\r\nTHEN 7\r\nWHEN "A31_101" = 1\r\nTHEN 0.2\r\nWHEN "A31_101" = 2\r\nTHEN 2\r\nWHEN "A31_101" = 3\r\nTHEN 3.6\r\nWHEN "A31_101" = 4\r\nTHEN 7\r\nWHEN "A31_101" = 5\r\nTHEN 14\r\nWHEN "A31_101" = 6\r\nTHEN 25\r\nWHEN "A31_201" = 1\r\nTHEN 0.2\r\nWHEN "A31_201" = 2\r\nTHEN 2\r\nWHEN "A31_201" = 3\r\nTHEN 3.6\r\nWHEN "A31_201" = 4\r\nTHEN 7\r\nWHEN "A31_201" = 5\r\nTHEN 14\r\nWHEN "A31_201" = 6\r\nTHEN 25\r\nWHEN "A31_301" = 1\r\nTHEN 0.2\r\nWHEN "A31_301" = 2\r\nTHEN 2\r\nWHEN "A31_301" = 3\r\nTHEN 3.6\r\nWHEN "A31_301" = 4\r\nTHEN 7\r\nWHEN "A31_301" = 5\r\nTHEN 14\r\nWHEN "A31_301" = 6\r\nTHEN 25\r\nWHEN "A31_401" = 1\r\nTHEN 0.2\r\nWHEN "A31_401" = 2\r\nTHEN 2\r\nWHEN "A31_401" = 3\r\nTHEN 3.6\r\nWHEN "A31_401" = 4\r\nTHEN 7\r\nWHEN "A31_401" = 5\r\nTHEN 14\r\nWHEN "A31_401" = 6\r\nTHEN 25\r\nWHEN "A31_105" = 1\r\nTHEN 0.2\r\nWHEN "A31_105" = 2\r\nTHEN 2\r\nWHEN "A31_105" = 3\r\nTHEN 3.6\r\nWHEN "A31_105" = 4\r\nTHEN 7\r\nWHEN "A31_105" = 5\r\nTHEN 14\r\nWHEN "A31_105" = 6\r\nTHEN 25\r\nWHEN "A31_205" = 1\r\nTHEN 0.2\r\nWHEN "A31_205" = 2\r\nTHEN 2\r\nWHEN "A31_205" = 3\r\nTHEN 3.6\r\nWHEN "A31_205" = 4\r\nTHEN 7\r\nWHEN "A31_205" = 5\r\nTHEN 14\r\nWHEN "A31_205" = 6\r\nTHEN 25\r\nWHEN "A31_405" = 1\r\nTHEN 0.2\r\nWHEN "A31_405" = 2\r\nTHEN 2\r\nWHEN "A31_405" = 3\r\nTHEN 3.6\r\nWHEN "A31_405" = 4\r\nTHEN 7\r\nWHEN "A31_405" = 5\r\nTHEN 14\r\nWHEN "A31_405" = 6\r\nTHEN 25\r\nEND',
                "OUTPUT": os.path.join(output_directory, "kouzui_merged.gpkg"),
            },
        )

        # TO DO: remove fields and keep only fid and depth

        # TO DO: debug to force delete files in TEMP
        # shutil.rmtree(extracted_dir)
