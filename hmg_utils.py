"""Hazard Map Game plugin utility functions."""

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
)
from qgis.PyQt.QtGui import QPainter
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


def merge_shapefiles(shapefiles: list, output_path: str, addfields="", add_data=False):
    """merge all shapefiles given in a file path list into a single geopackage file
    addfields option is fill with '-addfields' if desired. default NULL.
    """
    layer_name = os.path.splitext(os.path.basename(output_path))[0]

    if add_data:
        # add data to existing output geopackage file
        for shp in shapefiles:
            cmd = (
                f"ogr2ogr -lco ENCODING=cp932"
                f" -oo ENCODING=cp932 -nln {layer_name} -f GPKG"
                f" -append {addfields} -update -makevalid"
                f" {output_path} {shp}"
            )
            subprocess.run(
                cmd,
                shell=True,
                check=True,
            )
    else:
        # create new geopackage output
        cmd = (
            f"ogr2ogr -lco ENCODING=cp932 -oo ENCODING=cp932 -nln {layer_name} -f GPKG "
            f"-makevalid {output_path}"
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
                f" -append {addfields} -update -makevalid"
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
    QgsProject.instance().addMapLayer(xyz_layer, False)
    QgsProject.instance().layerTreeRoot().addLayer(xyz_layer)

    return xyz_layer


def _layer_group_name(layer_name: str):
    if (
        layer_name == "mesh_score"
        or layer_name.startswith("mesh_score_")
        or layer_name == "hazard_score"
        or layer_name.startswith("label_")
        or layer_name == "waku"
    ):
        return "HMG｜点数・ラベル"
    if layer_name.startswith("seamless_"):
        return "HMG｜リスク値"
    if layer_name.startswith("basemap_"):
        return "HMG｜背景地図"
    return None


def _move_layer_node(layer, target_group, index=None):
    root = QgsProject.instance().layerTreeRoot()
    node = root.findLayer(layer.id())
    if node is None:
        return
    if node.parent() is target_group and index is None:
        return
    cloned_node = node.clone()
    node.parent().removeChildNode(node)
    if index is None:
        target_group.addChildNode(cloned_node)
    else:
        target_group.insertChildNode(index, cloned_node)


def configure_hmg_layer_tree() -> None:
    """HMGレイヤーを用途別に整理し、最終確認向けの表示へ統一する。

    HMG以外のレイヤーは削除せず非表示にする。背景は陰影図を標準地図より
    上に置き、乗算・不透明度80%で表示する。
    """

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group_names = ["HMG｜点数・ラベル", "HMG｜リスク値", "HMG｜背景地図"]
    groups = {}
    for position, name in enumerate(group_names):
        group = root.findGroup(name)
        if group is None:
            group = root.insertGroup(position, name)
        groups[name] = group

    for layer in list(project.mapLayers().values()):
        group_name = _layer_group_name(layer.name())
        node = root.findLayer(layer.id())
        if group_name is None:
            if node:
                node.setItemVisibilityChecked(False)
            continue
        _move_layer_node(layer, groups[group_name])

    score_group = groups["HMG｜点数・ラベル"]
    risk_group = groups["HMG｜リスク値"]
    background_group = groups["HMG｜背景地図"]
    score_group.setExpanded(True)
    risk_group.setExpanded(False)
    background_group.setExpanded(True)

    for layer in project.mapLayers().values():
        node = root.findLayer(layer.id())
        if node is None:
            continue
        name = layer.name()
        if name == "mesh_score" or name.startswith("label_") or name == "waku":
            node.setItemVisibilityChecked(True)
        elif name.startswith("mesh_score_") or name.startswith("seamless_"):
            node.setItemVisibilityChecked(False)

    standard_layers = project.mapLayersByName("basemap_standard")
    if standard_layers:
        standard = standard_layers[0]
        standard.setOpacity(1.0)
        node = root.findLayer(standard.id())
        node.setItemVisibilityChecked(True)
        _move_layer_node(standard, background_group, 2)

    relief_layers = project.mapLayersByName("basemap_relief")
    if relief_layers:
        relief = relief_layers[0]
        node = root.findLayer(relief.id())
        node.setItemVisibilityChecked(False)
        _move_layer_node(relief, background_group, 1)

    hillshade_layers = project.mapLayersByName("basemap_hillshade")
    if hillshade_layers:
        hillshade = hillshade_layers[0]
        hillshade.setOpacity(0.8)
        try:
            multiply_mode = QPainter.CompositionMode.CompositionMode_Multiply
        except AttributeError:
            multiply_mode = QPainter.CompositionMode_Multiply
        hillshade.setBlendMode(multiply_mode)
        node = root.findLayer(hillshade.id())
        node.setItemVisibilityChecked(True)
        _move_layer_node(hillshade, background_group, 0)
