import glob
import os
import subprocess
import zipfile
from osgeo import ogr

from qgis.core import QgsProject, QgsVectorLayer


def unpack_zips_from_dir(target_dir: str, extracted_dir: str):
    """unpack all zip files in target_dir to extract_dir"""
    zips = [
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.endswith(".zip")
    ]

    os.mkdir(extracted_dir)

    for zip_filename in zips:
        extract_sjis_zip(zip_filename, extracted_dir)


def get_shapefiles_from_dir(target_dir: str) -> list:
    """return a list of shapefiles path from target dir
    subfolders included"""
    shapefiles = []
    for root, dirs, files in os.walk(target_dir):
        shp_files = glob.glob(os.path.join(root, "*.shp"))
        shapefiles.extend(shp_files)
    return shapefiles


def extract_sjis_zip(src_zip: str, dest: str) -> None:
    """SJIS の zip ファイルをファイル名の文字化けを避けて展開する"""
    with zipfile.ZipFile(src_zip) as zfile:
        for info in zfile.infolist():
            _rename(info)
            zfile.extract(info, dest)


def _rename(info: zipfile.ZipInfo) -> None:
    """ヘルパー: `ZipInfo` の中身をデコードし直す"""
    LANG_ENC_FLAG = 0x800
    encoding = "utf-8" if info.flag_bits & LANG_ENC_FLAG else "cp437"
    info.filename = info.filename.encode(encoding).decode("cp932")


def add_vlayer_from_file(path: str, layername: str):
    """SAGAアルゴリズムの出力ファイルを一時ファイルにする時、OUTPUTがファイルパスなので、
    ファイルからベクタレイヤをQGISに追加する"""
    QgsProject.instance().addMapLayer(QgsVectorLayer(path, layername, "ogr"))


def geom_type_from_shp(input_shp: str) -> str:
    shapefile = ogr.Open(input_shp)
    layer = shapefile.GetLayer()

    for feature in layer:
        geometry = feature.GetGeometryRef()
        return geometry.GetGeometryName()


def merge_shapefiles(shapefiles: list, output_path: str):
    """merge all shapefiles given in a file path list into a single geopackage file"""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    cmd = (
        f"ogr2ogr -lco ENCODING=cp932 -oo ENCODING=cp932 -nln {layer_name} -f GPKG "
        f"{output_path}"
        f" {shapefiles[0]}"
    )
    subprocess.run(
        cmd,
        shell=True,
        check=True,
    )

    for shp in shapefiles[1:]:
        cmd = (
            f"ogr2ogr -lco ENCODING=cp932"
            f" -oo ENCODING=cp932 -nln {layer_name} -f GPKG -append -update"
            f" {output_path} {shp}"
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )
