import processing
import csv

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsRectangle,
    QgsProject,
    QgsVectorLayer,
    QgsProcessing,
)

from qgis.utils import iface


def _get_a1_paper_size():
    return [0.841, 0.584]  # in meters


def _create_grid(grid_extent_str: str, grid_map_size: float) -> QgsVectorLayer:
    output_layer = processing.run(
        "native:creategrid",
        {
            "TYPE": 2,
            "EXTENT": grid_extent_str,
            "HSPACING": grid_map_size,
            "VSPACING": grid_map_size,
            "HOVERLAY": 0,
            "VOVERLAY": 0,
            "CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
    )["OUTPUT"]

    return output_layer


def _add_rect_as_a_layer(rect: QgsRectangle, layer_name: str):
    """QgsRectangleをレイヤーとして追加する"""
    rect_layer = QgsVectorLayer("Polygon?crs=epsg:3857", layer_name, "memory")
    provider = rect_layer.dataProvider()
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromRect(rect))
    provider.addFeatures([feature])
    QgsProject.instance().addMapLayer(rect_layer)
    rect_layer.setOpacity(0.5)


def _generate_waku_rectangle(
    center_x: float,
    center_y: float,
    a1_width: float,
    a1_height: float,
    scale: float,
):
    """create a rectangle called 'waku' which fit to paper size (here a1)
    and add to map"""
    waku_rec = QgsRectangle(
        center_x - a1_width * scale / 2,
        center_y - a1_height * scale / 2,
        center_x + a1_width * scale / 2,
        center_y + a1_height * scale / 2,
    )

    iface.mapCanvas().setExtent(waku_rec)
    iface.mapCanvas().refresh()
    _add_rect_as_a_layer(waku_rec, "waku")


def generate_mesh_point(
    center_x: float, center_y: float, nb_mesh1: int, nb_mesh2: int, orientation: str
) -> QgsVectorLayer:
    scale = 25000
    grid_map_size = 6 * scale / 100

    # move center point coordinates from 1/4 mesh size
    grid_center_x = center_x + (grid_map_size / 4)
    grid_center_y = center_y + (grid_map_size / 4)

    mesh_rows_col = [nb_mesh1, nb_mesh2]
    a1_size = _get_a1_paper_size()

    # default : 横
    nrows = min(mesh_rows_col)
    ncolumns = max(mesh_rows_col)
    a1_height = min(a1_size)
    a1_width = max(a1_size)

    if orientation == "縦":
        nrows = max(mesh_rows_col)
        ncolumns = min(mesh_rows_col)
        a1_height = max(a1_size)
        a1_width = min(a1_size)

    grid_extent_str = (
        f"{grid_center_x - (grid_map_size * ncolumns / 2)},"
        f" {grid_center_x + (grid_map_size * ncolumns / 2)},"
        f"{grid_center_y - (grid_map_size * nrows / 2)},"
        f"{grid_center_y + (grid_map_size * nrows / 2)} [EPSG:3857]"
    )

    mesh_lyr = _create_grid(grid_extent_str, grid_map_size)

    # A1の紙のサイズに合わせてワクを作成
    _generate_waku_rectangle(grid_center_x, grid_center_y, a1_width, a1_height, scale)

    return mesh_lyr


def generate_mesh_city(
    pref: str, city: str, pref_city_csv: str, fix_scale_threshold: bool
) -> QgsVectorLayer:
    space = 200  # 余白
    mesh_size = 0.06  # メッシュのサイズ=6cm

    # A1の紙のサイズ
    a1_size = _get_a1_paper_size()

    # スケールの閾値
    scale_threshold = 25000

    # メッシュ数
    long_size_n = 12
    short_size_n = 8

    with open(pref_city_csv, "r") as f:
        reader = csv.DictReader(f)
        bbox = [
            [row["x_min"], row["x_max"], row["y_min"], row["y_max"]]
            for row in reader
            if row["KNAME"] == pref and row["NAME"] == city
        ][0]

    grid_x_min = float(bbox[0]) - space
    grid_x_max = float(bbox[1]) + space
    grid_y_min = float(bbox[2]) - space
    grid_y_max = float(bbox[3]) + space

    center_x = (grid_x_max - grid_x_min) / 2 + grid_x_min
    center_y = (grid_y_max - grid_y_min) / 2 + grid_y_min

    size_x = grid_x_max - grid_x_min
    size_y = grid_y_max - grid_y_min

    long_side = max([size_x, size_y])

    scale = long_side / (mesh_size * long_size_n)
    grid_map_size = long_side / long_size_n

    if scale < scale_threshold or fix_scale_threshold is True:
        # 縮尺が25000以下の場合,強制的に25000にする
        # 25000以上の場合,強制的に25000にするチェックボックスがTrueの場合
        scale = scale_threshold
        grid_map_size = mesh_size * scale_threshold

        if size_x >= size_y:
            grid_x_min = center_x - mesh_size * scale_threshold * (long_size_n / 2)
            grid_x_max = center_x + mesh_size * scale_threshold * (long_size_n / 2)
            grid_y_min = center_y - mesh_size * scale_threshold * (short_size_n / 2)
            grid_y_max = center_y + mesh_size * scale_threshold * (short_size_n / 2)
        else:
            grid_x_min = center_x - mesh_size * scale_threshold * (short_size_n / 2)
            grid_x_max = center_x + mesh_size * scale_threshold * (short_size_n / 2)
            grid_y_min = center_y - mesh_size * scale_threshold * (long_size_n / 2)
            grid_y_max = center_y + mesh_size * scale_threshold * (long_size_n / 2)

    if size_x >= size_y:
        # 向き：横
        # 中心点からの距離をピッタリにすると、グリッドが一個多くできることがあるので、0.01mを引いている
        grid_extent_str = (
            f"{grid_x_min}, {grid_x_max},"
            f"{center_y - grid_map_size * (short_size_n / 2 - 0.01)},"
            f"{center_y + grid_map_size * (short_size_n / 2 - 0.01)} [EPSG:3857]"
        )
        a1_height = min(a1_size)
        a1_width = max(a1_size)

    else:
        # 向き：縦
        grid_extent_str = (
            f"{center_x - grid_map_size * (short_size_n / 2 - 0.01)}, "
            f"{center_x + grid_map_size * (short_size_n / 2 - 0.01)},"
            f"{grid_y_min},{grid_y_max} [EPSG:3857]"
        )
        a1_height = max(a1_size)
        a1_width = min(a1_size)

    # A1の紙のサイズに合わせてワクを作成
    _generate_waku_rectangle(center_x, center_y, a1_width, a1_height, scale)

    # メッシュ作成
    mesh_lyr = _create_grid(grid_extent_str, grid_map_size)

    return mesh_lyr


def exclude_offshore_mesh(
    mesh_lyr: QgsVectorLayer, landuse_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # clip landuse to only mesh area
    landuse_clipped = processing.run(
        "native:clip",
        {
            "INPUT": landuse_lyr,
            "OVERLAY": mesh_lyr,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # reproject to mesh CRS
    proj_operation = (
        "+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step"
        " +proj=webmerc +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84"
    )
    landuse_reprojected = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": landuse_clipped,
            "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
            "OPERATION": proj_operation,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # intersect with mesh CRS
    landuse_intersected = processing.run(
        "native:intersection",
        {
            "INPUT": mesh_lyr,
            "OVERLAY": landuse_reprojected,
            "INPUT_FIELDS": [],
            "OVERLAY_FIELDS": ["土地利用種"],
            "OVERLAY_FIELDS_PREFIX": "",
            "OUTPUT": "TEMPORARY_OUTPUT",
            "GRID_SIZE": None,
        },
    )["OUTPUT"]

    # remove water landuse (1100 and 1500 values of 土地利用種)
    inland_meshes = processing.run(
        "native:extractbyexpression",
        {
            "INPUT": landuse_intersected,
            "EXPRESSION": " \"土地利用種\" NOT IN ( '1100' , '1500' )",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # dissolve by hmg mesh
    inland_meshes_dissolved = processing.run(
        "native:dissolve",
        {
            "INPUT": inland_meshes,
            "FIELD": ["id"],
            "SEPARATE_DISJOINT": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # calculate inland area
    inland_meshes_area = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": inland_meshes_dissolved,
            "FIELD_NAME": "inland_area",
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": " $area ",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # join inland area to input hmg mesh
    mesh_inland_area = processing.run(
        "native:joinattributestable",
        {
            "INPUT": mesh_lyr,
            "FIELD": "id",
            "INPUT_2": inland_meshes_area,
            "FIELD_2": "id",
            "FIELDS_TO_COPY": ["inland_area"],
            "METHOD": 1,
            "DISCARD_NONMATCHING": False,
            "PREFIX": "",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # keep only mesh which have >= 10% of inland area
    offshore_excluded_meshes = processing.run(
        "native:extractbyexpression",
        {
            "INPUT": mesh_inland_area,
            "EXPRESSION": ' "inland_area" / $area >= 0.1',
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    return offshore_excluded_meshes
