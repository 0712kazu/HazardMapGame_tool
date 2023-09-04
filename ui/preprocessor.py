import os
import glob
import subprocess
import shutil

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.PyQt import uic
from qgis.utils import iface

from constants import INPUT_DIR_TOCHIRIYOU, INPUT_DIR_ZISUBERI, OUTPUT_DIR


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
            error_message = "シームレスフォルダーが設定してない。"
            QMessageBox.information(None, "エラー", f"エラーが発生しました。\n\n{error_message}")
            return
        if self.main.QgsFileWidget_tochiriyou.filePath():
            self.preprocess_tochiriyou()
        if self.main.QgsFileWidget_kozui.filePath():
            self.preprocess_kozui()

    def preprocess_tochiriyou(self):
        root_directory = self.main.QgsFileWidget_tochiriyou.filePath()
        output_directory = self.main.FileWidgetSeamlessDir.filePath()

        zips = [
            os.path.join(root_directory, f)
            for f in os.listdir(root_directory)
            if f.endswith(".zip")
        ]
        extracted_dir = os.path.join(root_directory, "temp")
        os.mkdir(extracted_dir)

        [shutil.unpack_archive(zip_filename, extracted_dir) for zip_filename in zips]

        shapefiles = [
            os.path.join(extracted_dir, f)
            for f in os.listdir(extracted_dir)
            if f.endswith(".shp")
        ]
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

    def preprocess_kozui(self):
        print("KOZUI!")
