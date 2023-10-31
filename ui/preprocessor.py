import glob
import os
import shutil
import subprocess

from osgeo_utils.ogrmerge import process as ogr_merge
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox


from constants import (
    INPUT_DIR_KOZUI,
    INPUT_DIR_JISUBERI,
    INPUT_DIR_SAIGAI,
    INPUT_DIR_TOCHIRIYOU,
    INPUT_DIR_SHIKUCHOSON,
    OUTPUT_DIR,
)
from utils import (
    get_shapefiles_from_dir,
    unpack_zips_from_dir,
    geom_type_from_shp,
    merge_shapefiles,
)


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
            (INPUT_DIR_JISUBERI, self.main.QgsFileWidget_jisuberi),
            (INPUT_DIR_SAIGAI, self.main.QgsFileWidget_saigai),
            (INPUT_DIR_TOCHIRIYOU, self.main.QgsFileWidget_tochiriyou),
            (INPUT_DIR_SHIKUCHOSON, self.main.QgsFileWidget_cities),
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
        if self.main.QgsFileWidget_kozui.filePath():
            self.preprocess_kozui(
                self.main.QgsFileWidget_kozui.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )
        if self.main.QgsFileWidget_jisuberi.filePath():
            self.preprocess_jisuberi(
                self.main.QgsFileWidget_jisuberi.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )
        if self.main.QgsFileWidget_saigai.filePath():
            self.preprocess_saigai(
                self.main.QgsFileWidget_saigai.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )
        if self.main.QgsFileWidget_tochiriyou.filePath():
            self.preprocess_tochiriyou(
                self.main.QgsFileWidget_tochiriyou.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )
        if self.main.QgsFileWidget_shikuchoson.filePath():
            self.preprocess_shikuchoson(
                self.main.QgsFileWidget_shikuchoson.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

    def preprocess_tochiriyou(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, "tochiriyou_merged.gpkg")
        )

        shutil.rmtree(extracted_dir)

    def preprocess_kozui(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        merged_shapefiles = os.path.join(output_directory, "kouzui_merged.gpkg")

        # merge all shp to gpkg
        ogr_merge(["-o", merged_shapefiles, "-single", "-f", "GPKG"] + shapefiles)
        shutil.rmtree(extracted_dir)

    def preprocess_jisuberi(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)

        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, "jisuberi_merged.gpkg")
        )

        shutil.rmtree(extracted_dir)

    def preprocess_saigai(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)

        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, "saigai_merged.gpkg")
        )

        shutil.rmtree(extracted_dir)

    def preprocess_shikuchoson(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")

        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(root_directory)

        if len(shapefiles) != 1:
            error_message = "1 shapefile is required for shikuchoson\n"
            error_message += str(len(shapefiles)) + " shapefiles found."
            QMessageBox.information(None, "エラー", f"エラーが発生しました。\n\n{error_message}")
            return

        layer_name = os.path.splitext(os.path.basename(shapefiles[0]))[0]
        tmp_cities_file = os.path.join(output_directory, "tmp_cities.gpkg")
        # reproject to EPSG:3857 and order by GCODE
        sql = "SELECT ST_Union(geometry) AS geometry,* "
        sql += f"FROM {layer_name} GROUP BY GCODE ORDER BY GCODE"
        cmd = (
            f"ogr2ogr -lco ENCODING=UTF-8 -nln tmp_cities -t_srs EPSG:3857 -f GPKG "
            f'-nlt PROMOTE_TO_MULTI -dialect sqlite -sql "{sql}" '
            f"{tmp_cities_file}"
            f" {shapefiles[0]}"
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        # calculate bounding box and save to CSV
        sql = "SELECT GCODE,KNAME,NAME,KKANA,KANA,"
        sql += "ST_MinX(geometry) AS x_min,ST_MaxX(geometry) AS x_max, "
        sql += "ST_MinY(geometry) AS y_min,ST_MinY(geometry) AS y_max, "
        sql += "ST_X(ST_PointOnSurface(geometry)) as center_x, "
        sql += "ST_Y(ST_PointOnSurface(geometry)) as center_y "
        sql += "FROM tmp_cities"

        cmd = (
            f"ogr2ogr {os.path.join(output_directory,'shikuchoson.csv')} "
            f"{tmp_cities_file} "
            f'-nlt PROMOTE_TO_MULTI -dialect sqlite -sql "{sql}" '
            f"-f CSV "
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        # remove tmp files
        os.remove(tmp_cities_file)
        shutil.rmtree(extracted_dir)
