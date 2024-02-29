import glob
import os
import subprocess
import zipfile
from osgeo import ogr

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsRasterLayer,
    QgsLayerTreeLayer,
)
from qgis.utils import iface


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
    try:
        info.filename = info.filename.encode(encoding).decode("cp932")
    except UnicodeDecodeError as e:
        # Wrong byte included in filename (eg: 0x91)
        print(f"Unable to decode {info.filename}\n{e}")


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


def merge_shapefiles(shapefiles: list, output_path: str, addfields=""):
    """merge all shapefiles given in a file path list into a single geopackage file
    addfields option is fill with '-addfields' if desired. default NULL.
    """
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
            f" -oo ENCODING=cp932 -nln {layer_name} -f GPKG"
            f" -append {addfields} -update"
            f" {output_path} {shp}"
        )
        subprocess.run(
            cmd,
            shell=True,
            check=True,
        )


def add_to_map(layer: QgsVectorLayer, layer_name: str) -> None:
    layer.setName(layer_name)
    QgsProject.instance().addMapLayer(layer)
    layer.setOpacity(0.5)


def remove_layer(layer_name: str) -> None:
    if QgsProject.instance().mapLayersByName(layer_name):
        remove_lyr = QgsProject.instance().mapLayersByName(layer_name)[0]
        QgsProject.instance().removeMapLayer(remove_lyr.id())


def set_map_canvas_to_webmercator():
    webmercator_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    if iface.mapCanvas().mapSettings().destinationCrs() != webmercator_crs:
        iface.mapCanvas().setDestinationCrs(webmercator_crs)


def get_layer_orientation(layer: QgsVectorLayer) -> str:
    """return layer extent orientation"""
    rectangle = layer.extent()
    if rectangle.width() >= rectangle.height():
        return "landscape"
    else:
        return "portrait"


def add_xyz_basemap_layer(url: str, layer_name: str) -> QgsRasterLayer:
    """add a xyz layer from URL, at the bottom of layer tree"""
    url = f"type=xyz&url={url}&zmax=15&zmin=0&crs=EPSG3857"
    xyz_layer = QgsRasterLayer(url, layer_name, "wms")
    QgsProject.instance().addMapLayer(xyz_layer)

    return xyz_layer


def find(list: list, x) -> int:
    """
    https://note.nkmk.me/python-list-index/
    配列から要素を検索し、存在すればそのインデックスを返す
    存在しなければ-1を返す
    Args:
        list ([type]): 検索対象の配列
        x ([type]): 検索する値
    Returns:
        int: 見つかった最初の要素のインデックス
    """
    return list.index(x) if x in list else -1
