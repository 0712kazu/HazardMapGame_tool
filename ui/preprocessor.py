import glob
import os
import shutil
import subprocess
import csv

from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox


from constants import (
    INPUT_DIR_TATUMAKI,
    INPUT_DIR_KOZUI,
    INPUT_DIR_SEDIMENTS,
    INPUT_DIR_TSUNAMI,
    INPUT_DIR_JISUBERI,
    INPUT_DIR_SAIGAI,
    INPUT_DIR_SURGE,
    INPUT_DIR_EARTHQUAKE,
    INPUT_DIR_SLOPE,
    INPUT_DIR_REFUGE,
    INPUT_DIR_TOCHIRIYOU,
    INPUT_DIR_SHIKUCHOSON,
    SEAMLESS_FILE_TORNADO,
    SEAMLESS_FILE_FLOOD,
    SEAMLESS_FILE_LANDSLIP,
    SEAMLESS_FILE_SEDIMENTS,
    SEAMLESS_FILE_TSUNAMI,
    SEAMLESS_FILE_DISASTER,
    SEAMLESS_FILE_SURGE,
    SEAMLESS_FILE_EARTHQUAKE,
    SEAMLESS_FILE_SLOPE,
    SEAMLESS_FILE_REFUGE,
    SEAMLESS_FILE_CITIES,
    SEAMLESS_FILE_LANDUSE,
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

        self.seamless_processed = []

    def load_elements_files_from_dir(self):
        """
        指定されたフォルダから複数のファイルを探し見つけたらFileWidgetに反映する
        """
        selected_dir = QFileDialog.getExistingDirectory(self.main, "フォルダを選択")

        for folder_name, filewidget in (
            (INPUT_DIR_TATUMAKI, self.main.QgsFileWidget_tatumaki),
            (INPUT_DIR_KOZUI, self.main.QgsFileWidget_kozui),
            (INPUT_DIR_SEDIMENTS, self.main.QgsFileWidget_sediments),
            (INPUT_DIR_TSUNAMI, self.main.QgsFileWidget_tsunami),
            (INPUT_DIR_JISUBERI, self.main.QgsFileWidget_jisuberi),
            (INPUT_DIR_SAIGAI, self.main.QgsFileWidget_saigai),
            (INPUT_DIR_SURGE, self.main.QgsFileWidget_surge),
            (INPUT_DIR_EARTHQUAKE, self.main.QgsFileWidget_earthquake),
            (INPUT_DIR_SLOPE, self.main.QgsFileWidget_slope),
            (INPUT_DIR_REFUGE, self.main.QgsFileWidget_refuge),
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
            error_message = "エラーが発生しました。\n\n"
            error_message += "シームレスフォルダーが設定していません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        # process list
        self.seamless_processed = []
        if self.main.QgsFileWidget_tatumaki.filePath():
            self.preprocess_tatumaki(
                self.main.QgsFileWidget_tatumaki.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_kozui.filePath():
            self.preprocess_kozui(
                self.main.QgsFileWidget_kozui.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_sediments.filePath():
            self.preprocess_sediments(
                self.main.QgsFileWidget_sediments.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_tsunami.filePath():
            self.preprocess_tsunami(
                self.main.QgsFileWidget_tsunami.filePath(),
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

        if self.main.QgsFileWidget_surge.filePath():
            self.preprocess_surge(
                self.main.QgsFileWidget_surge.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_earthquake.filePath():
            self.preprocess_earthquake(
                self.main.QgsFileWidget_earthquake.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_slope.filePath():
            self.preprocess_slope(
                self.main.QgsFileWidget_slope.filePath(),
                self.main.FileWidgetSeamlessDir.filePath(),
            )

        if self.main.QgsFileWidget_refuge.filePath():
            self.preprocess_refuge(
                self.main.QgsFileWidget_refuge.filePath(),
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

        message = "シムレスデータの作成が完了しました。\n"
        for seamless_data in self.seamless_processed:
            message += f"{seamless_data}\n"
        QMessageBox.information(None, "完了", message)

    def preprocess_tochiriyou(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 土地利用 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_LANDUSE)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_LANDUSE)

    def preprocess_kozui(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            QMessageBox.information(None, "お知らせ", "No shapefile in 洪水 directory.")
            shutil.rmtree(extracted_dir)
            return
        merged_shapefiles = os.path.join(output_directory, SEAMLESS_FILE_FLOOD)

        # merge all shp to gpkg
        merge_shapefiles(shapefiles, merged_shapefiles, "-addfields")
        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_FLOOD)

    def preprocess_sediments(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 土砂 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_SEDIMENTS)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_SEDIMENTS)

    def preprocess_tsunami(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 津波 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_TSUNAMI)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_TSUNAMI)

    def preprocess_jisuberi(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 地すべり directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_LANDSLIP)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_LANDSLIP)

    def preprocess_saigai(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 災害危険 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return

        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_DISASTER)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_DISASTER)

    def preprocess_surge(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 高潮 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_SURGE)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_SURGE)

    def preprocess_earthquake(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 地震 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_EARTHQUAKE)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_EARTHQUAKE)

    def preprocess_slope(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(extracted_dir)
        if len(shapefiles) == 0:
            message = "No shapefile in 傾斜度 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return
        # get only polygon shapefiles
        for shapefile in shapefiles:
            if geom_type_from_shp(shapefile) != "POLYGON":
                shapefiles.remove(shapefile)

        # merge all shp to gpkg
        merge_shapefiles(
            shapefiles, os.path.join(output_directory, SEAMLESS_FILE_SLOPE)
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_SLOPE)

    def preprocess_refuge(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)

        csvfiles = []
        for root, dirs, files in os.walk(extracted_dir):
            csv_files = glob.glob(os.path.join(root, "*.csv"))
            csvfiles.extend(csv_files)

        if len(csvfiles) == 0:
            message = "No CSV file in 避難施設 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return

        # get only CSV with 緯度/経度 column
        for csv_file in csvfiles:
            with open(csv_file, "r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)

                # Read the header row
                header = next(reader, None)

                # Check if 'x' and 'y' columns are present
                if "緯度" in header and "経度" in header:
                    refuge_csv_file = csv_file

        if not refuge_csv_file:
            message = "No valid CSV file in 避難施設 directory."
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return

        cmd = (
            f"ogr2ogr -t_srs EPSG:3857 -f GPKG "
            "-oo X_POSSIBLE_NAMES=経度 -oo Y_POSSIBLE_NAMES=緯度"
            f" -nln {SEAMLESS_FILE_REFUGE.split('.')[0]}"
            f" {os.path.join(output_directory, SEAMLESS_FILE_REFUGE)}"
            f" {refuge_csv_file} -s_srs EPSG:4326"
        )

        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        shutil.rmtree(extracted_dir)
        self.seamless_processed.append(SEAMLESS_FILE_REFUGE)

    def preprocess_shikuchoson(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")

        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)
        shapefiles = get_shapefiles_from_dir(root_directory)

        if len(shapefiles) != 1:
            error_message = "エラーが発生しました。\n\n"
            error_message += "1 shapefile is required for shikuchoson\n"
            error_message += str(len(shapefiles)) + " shapefiles found."
            QMessageBox.information(None, "エラー", error_message)
            shutil.rmtree(extracted_dir)
            return

        layer_name = os.path.splitext(os.path.basename(shapefiles[0]))[0]
        tmp_cities_file = os.path.join(output_directory, "tmp_cities.gpkg")
        # reproject to EPSG:3857 and order by GCODE
        sql = "SELECT ST_Union(geometry) AS geometry,* "
        sql += f"FROM {layer_name} WHERE KNAME != '' GROUP BY GCODE ORDER BY GCODE"
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
        sql += "ST_MinX(geometry) AS x_min, ST_MaxX(geometry) AS x_max, "
        sql += "ST_MinY(geometry) AS y_min, ST_MaxY(geometry) AS y_max, "
        sql += "ST_X(ST_PointOnSurface(geometry)) as center_x, "
        sql += "ST_Y(ST_PointOnSurface(geometry)) as center_y "
        sql += "FROM tmp_cities"

        cmd = (
            f"ogr2ogr {os.path.join(output_directory,SEAMLESS_FILE_CITIES)} "
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
        self.seamless_processed.append(SEAMLESS_FILE_CITIES)

    def preprocess_tatumaki(self, root_directory: str, output_directory: str):
        extracted_dir = os.path.join(root_directory, "temp")
        if not os.path.exists(extracted_dir):
            unpack_zips_from_dir(root_directory, extracted_dir)

        extracted_shapefiles = get_shapefiles_from_dir(extracted_dir)

        # get only point shapefiles
        shapefiles = []
        for shapefile in extracted_shapefiles:
            if geom_type_from_shp(shapefile) == "POINT":
                shapefiles.append(shapefile)

        if len(shapefiles) == 0:
            message = "No point shapefile in 竜巻 directory"
            QMessageBox.information(None, "お知らせ", message)
            shutil.rmtree(extracted_dir)
            return

        # merge all shp to gpkg
        tmp_tornado_merged = os.path.join(extracted_dir, "tmp_" + SEAMLESS_FILE_TORNADO)
        merge_shapefiles(shapefiles, tmp_tornado_merged)

        # make 500m buffer
        sql = "SELECT ST_Union(ST_Buffer(ST_Transform(geom, 32654), 500)) as geometry "
        sql += f"FROM tmp_{SEAMLESS_FILE_TORNADO.split('.')[0]}"

        cmd = (
            f"ogr2ogr {os.path.join(output_directory, SEAMLESS_FILE_TORNADO)} "
            f"{tmp_tornado_merged} "
            f'-nlt PROMOTE_TO_MULTI -dialect sqlite -sql "{sql}" '
            f"-nln {SEAMLESS_FILE_TORNADO.split('.')[0]} "
            f"-t_srs EPSG:3857 -f GPKG "
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )

        shutil.rmtree(extracted_dir)

        self.seamless_processed.append(SEAMLESS_FILE_TORNADO)
