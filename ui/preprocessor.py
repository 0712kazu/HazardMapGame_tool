import glob
import os
import shutil
import subprocess

from osgeo import gdal
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox

from constants import (
    INPUT_DIR_KOZUI,
    INPUT_DIR_TOCHIRIYOU,
    INPUT_DIR_ZISUBERI,
    OUTPUT_DIR,
)
from ui.utils import get_shapefiles_from_dir, unpack_zips_from_dir


class Preprocessor:
    def __init__(self, main: QDialog):
        self.main = main

        self.main.pushButton_run_2.clicked.connect(self.run)
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
        merged_shapefiles = os.path.join(output_directory, "kouzui_merged.gpkg")

        # merge all shapefiles in one
        # fix geometries
        # normalized with SQL
        cmd = [
            "ogr2ogr",
            "-lco",
            "ENCODING=cp932",
            "-oo",
            "ENCODING=cp932",
            "-nln",
            "kouzui_merged",
            "-dialect",
            "SQLITE",
            "-sql",
            self._make_depth_sql(shapefiles[0]),
            "-makevalid",
            "-f",
            "GPKG",
            merged_shapefiles,
            shapefiles[0],
        ]

        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        for shp in shapefiles[1:]:
            cmd = [
                "ogr2ogr",
                "-lco",
                "ENCODING=cp932",
                "-oo",
                "ENCODING=cp932",
                "-nln",
                "kouzui_merged",
                "-dialect",
                "SQLITE",
                "-sql",
                self._make_depth_sql(shp),
                "-makevalid",
                "-f",
                "GPKG",
                "-append",
                "-addfields",
                "-update",
                merged_shapefiles,
                shp,
            ]

            subprocess.run(
                cmd,
                shell=True,
                check=True,
            )
        shutil.rmtree(extracted_dir)

    def _make_depth_sql(self, input_geodata: str) -> str:
        """make sql formula to calculate depth field
        based on input field and specs"""

        kouzui_v1_fields = ["A31_001"]
        kouzui_v2_fields = [
            "A31_101",
            "A31_105",
            "A31_201",
            "A31_205",
            "A31_301",
            "A31_305",
            "A31_401",
            "A31_405",
        ]

        gdal_layer = gdal.OpenEx(input_geodata)
        lyr = gdal_layer.GetLayer(0)
        depth_sql = "SELECT geometry, CASE "

        # v1
        for field in kouzui_v1_fields:
            if lyr.GetLayerDefn().GetFieldIndex(field) != -1:
                depth_sql += (
                    f"WHEN {field} = 11 THEN 0.2 "
                    f"WHEN {field} = 12 THEN 0.7 "
                    f"WHEN {field} = 13 THEN 1.4 "
                    f"WHEN {field} = 14 THEN 3 "
                    f"WHEN {field} = 15 THEN 7 "
                    f"WHEN {field} = 21 THEN 0.2 "
                    f"WHEN {field} = 22 THEN 0.7 "
                    f"WHEN {field} = 23 THEN 1.4 "
                    f"WHEN {field} = 24 THEN 2.4 "
                    f"WHEN {field} = 25 THEN 3.4 "
                    f"WHEN {field} = 26 THEN 4.4 "
                    f"WHEN {field} = 27 THEN 7 "
                )

        for field in kouzui_v2_fields:
            if lyr.GetLayerDefn().GetFieldIndex(field) != -1:
                depth_sql += (
                    f"WHEN {field} = 1 THEN 0.2 "
                    f"WHEN {field} = 2 THEN 2 "
                    f"WHEN {field} = 3 THEN 3.6 "
                    f"WHEN {field} = 4 THEN 7 "
                    f"WHEN {field} = 5 THEN 14 "
                    f"WHEN {field} = 6 THEN 25 "
                )

        depth_sql += "END AS depth "
        depth_sql += f'FROM "{lyr.GetName()}"'

        return depth_sql
