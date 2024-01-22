import processing
from PyQt5.QtWidgets import QProgressBar, QMessageBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgisInterface

from qgis.core import QgsProcessingFeatureSourceDefinition as qpfsd

import constants
from utils import add_to_map


def _clip_with_valid_geometries(
    input_layer: QgsVectorLayer, overlay_layer: QgsVectorLayer
) -> QgsVectorLayer:
    clipped = processing.run(
        "native:clip",
        {
            "INPUT": QgsProcessingFeatureSourceDefinition(
                input_layer.source(),
                selectedFeaturesOnly=False,
                featureLimit=-1,
                flags=qpfsd.FlagOverrideDefaultGeometryCheck,
                geometryCheck=QgsFeatureRequest.GeometryNoCheck,
            ),
            "OVERLAY": overlay_layer,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]
    return clipped


def _handle_zero_polygon_hazard(
    mesh_lyr: QgsVectorLayer, target_field: str
) -> QgsVectorLayer:
    mesh_calculated = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": mesh_lyr,
            "FIELD_NAME": target_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": "0",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]
    message = f"対象領域にポリゴンが含めてないため「{target_field}」の値が0になります。"
    QMessageBox.information(None, "お知らせ", message)
    return mesh_calculated


def _sum_surfaces_intersect_meshes(
    seamless_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, calculate_field: str
) -> QgsVectorLayer:
    # fix_geometries
    seamless_fix = processing.run(
        "native:fixgeometries",
        {
            "INPUT": seamless_lyr,
            "METHOD": 1,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # reproject to 3857
    seamless_reprojected = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": seamless_fix,
            "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # Dissolve to avoid overlay polygon
    dissolve_field = []
    if calculate_field == constants.field_tsunami:
        dissolve_field = ["h_tsunami"]
    if calculate_field == constants.field_surge:
        dissolve_field = ["h_surge"]

    seamless_dissolved = processing.run(
        "native:dissolve",
        {
            "INPUT": seamless_reprojected,
            "FIELD": dissolve_field,
            "SEPARATE_DISJOINT": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # intersect with mesh
    seamless_mesh_intersect = processing.run(
        "native:intersection",
        {
            "INPUT": seamless_dissolved,
            "OVERLAY": mesh_lyr,
            "INPUT_FIELDS": [],
            "OVERLAY_FIELDS": ["id"],
            "OVERLAY_FIELDS_PREFIX": "mesh_",
            "OUTPUT": "TEMPORARY_OUTPUT",
            "GRID_SIZE": None,
        },
    )["OUTPUT"]

    # calculate area of intersect polygon
    area_formula = " area(@geometry) "

    if calculate_field == constants.field_tsunami:
        # for tsunami, multiply with tsunami rank
        area_formula = " area(@geometry) * h_tsunami"
    if calculate_field == constants.field_surge:
        # for storm surge, multiply with surge rank
        area_formula = " area(@geometry) * h_surge"

    seamless_mesh_intersect_area = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": seamless_mesh_intersect,
            "FIELD_NAME": "area",
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": area_formula,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # aggregate sum area for each mesh id
    seamless_area_by_mesh = processing.run(
        "native:aggregate",
        {
            "INPUT": seamless_mesh_intersect_area,
            "GROUP_BY": '"mesh_id"',
            "AGGREGATES": [
                {
                    "aggregate": "first_value",
                    "delimiter": ",",
                    "input": '"mesh_id"',
                    "length": 0,
                    "name": "mesh_id",
                    "precision": 0,
                    "sub_type": 0,
                    "type": 4,
                    "type_name": "int8",
                },
                {
                    "aggregate": "sum",
                    "delimiter": ",",
                    "input": '"area"',
                    "length": 0,
                    "name": calculate_field,
                    "precision": 0,
                    "sub_type": 0,
                    "type": 6,
                    "type_name": "double precision",
                },
            ],
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # join with origin mesh
    mesh_join_seamless_area = processing.run(
        "native:joinattributestable",
        {
            "INPUT": mesh_lyr,
            "FIELD": "id",
            "INPUT_2": seamless_area_by_mesh,
            "FIELD_2": "mesh_id",
            "FIELDS_TO_COPY": [calculate_field],
            "METHOD": 1,
            "DISCARD_NONMATCHING": False,
            "PREFIX": "",
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # populate null values with 0
    seamless_sql = (
        f'CASE WHEN "{calculate_field}" > 0 THEN "{calculate_field}" ELSE 0 END'
    )
    seamless_sum_mesh = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": mesh_join_seamless_area,
            "FIELD_NAME": calculate_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": seamless_sql,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    return seamless_sum_mesh


def _adjust_inland_score(layer: QgsVectorLayer, hazard_field: str) -> QgsVectorLayer:
    return processing.run(
        "native:fieldcalculator",
        {
            "INPUT": layer,
            "FIELD_NAME": hazard_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": f' "{hazard_field}"  /  "land_rate" ',
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]


def _make_depth_sql(kozui_layer: QgsVectorLayer) -> str:
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

    depth_sql = "SELECT geometry, CASE "

    for field in kouzui_v1_fields:
        if kozui_layer.fields().lookupField(field) != -1:
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
        if kozui_layer.fields().lookupField(field) != -1:
            depth_sql += (
                f"WHEN {field} = 1 THEN 0.2 "
                f"WHEN {field} = 2 THEN 2 "
                f"WHEN {field} = 3 THEN 3.6 "
                f"WHEN {field} = 4 THEN 7 "
                f"WHEN {field} = 5 THEN 14 "
                f"WHEN {field} = 6 THEN 25 "
            )

    depth_sql += "END AS depth "
    depth_sql += f"FROM {kozui_layer.name()}"

    return depth_sql


def seamless2hmg_kosui(
    kozui_lyr: QgsVectorLayer,
    waku_lyr: QgsVectorLayer,
    mesh_lyr: QgsVectorLayer,
    qgis_iface: QgisInterface,
) -> QgsVectorLayer:
    # Progression bar
    qgis_iface.messageBar().clearWidgets()
    progressMessageBar = qgis_iface.messageBar()
    progressbar = QProgressBar(progressMessageBar)
    progressMessageBar.pushWidget(progressbar)

    # Processing feedback
    def progress_changed(progress):
        progressbar.setValue(progress)

    f = QgsProcessingFeedback()
    f.progressChanged.connect(progress_changed)

    # extract intersected polygons to avoid clip intersect error
    kozui_extract = processing.run(
        "native:extractbylocation",
        {
            "INPUT": QgsProcessingFeatureSourceDefinition(
                kozui_lyr.source(),
                selectedFeaturesOnly=False,
                featureLimit=-1,
                flags=qpfsd.FlagOverrideDefaultGeometryCheck,
                geometryCheck=QgsFeatureRequest.GeometryNoCheck,
            ),
            "PREDICATE": [0],
            "INTERSECT": waku_lyr,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    kozui_cliped = processing.run(
        "native:clip",
        {
            "INPUT": kozui_extract,
            "OVERLAY": waku_lyr,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # Handle when there is no cliped features
    if kozui_cliped.featureCount() == 0:
        kozui_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_kozui)
        return kozui_mesh

    kozui_cliped_fixed = processing.run(
        "native:fixgeometries",
        {
            "INPUT": kozui_cliped,
            "METHOD": 1,  # strucutre
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(kozui_cliped_fixed, f"seamless_{constants.field_kozui}")

    # 標準化
    kozui_standard = processing.run(
        "qgis:executesql",
        {
            "INPUT_DATASOURCES": [kozui_cliped_fixed],
            "INPUT_QUERY": _make_depth_sql(kozui_cliped_fixed),
            "INPUT_UID_FIELD": "",
            "INPUT_GEOMETRY_FIELD": "",
            "INPUT_GEOMETRY_TYPE": None,
            "INPUT_GEOMETRY_CRS": None,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    opt = (
        "+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step"
        " +proj=webmerc +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84"
    )

    kozui_standard = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": kozui_standard,
            "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
            "OPERATION": opt,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # 20m間隔ポイントを作成
    pnt_lyr_raw = processing.run(
        "native:creategrid",
        {
            "TYPE": 0,
            "EXTENT": mesh_lyr.extent(),
            "HSPACING": 20,
            "VSPACING": 20,
            "HOVERLAY": 0,
            "VOVERLAY": 0,
            "CRS": waku_lyr.crs(),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # 空間Indexを作成
    print("Creating spatial index...")
    for lyr in [kozui_standard, pnt_lyr_raw, mesh_lyr]:
        processing.run("native:createspatialindex", {"INPUT": lyr})

    # Get only points intersects flood polygons
    pnt_lyr = processing.run(
        "native:clip",
        {
            "INPUT": pnt_lyr_raw,
            "OVERLAY": kozui_cliped_fixed,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    processing.run("native:createspatialindex", {"INPUT": pnt_lyr})

    print("ポイントに最大浸水深を結合...")
    max_dep_pnt = processing.run(
        "qgis:joinbylocationsummary",
        {
            "INPUT": pnt_lyr,
            "PREDICATE": [0],
            "JOIN": kozui_standard,
            "JOIN_FIELDS": ["depth"],
            "SUMMARIES": [3],  # max
            "DISCARD_NONMATCHING": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
        feedback=f,
    )["OUTPUT"]
    qgis_iface.messageBar().clearWidgets()
    max_dep_pnt.setName("tmp_point_cliped")
    QgsProject.instance().addMapLayer(max_dep_pnt)

    print("メッシュごとの最大浸水深合計を計算...")
    kozui_max_sum = processing.run(
        "qgis:joinbylocationsummary",
        {
            "INPUT": mesh_lyr,
            "PREDICATE": [0],
            "JOIN": max_dep_pnt,
            "JOIN_FIELDS": ["depth_max"],
            "SUMMARIES": [5],  # sum
            "DISCARD_NONMATCHING": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
        feedback=f,
    )["OUTPUT"]
    qgis_iface.messageBar().clearWidgets()

    print("属性名を変更...")
    kozui_renamed = processing.run(
        "native:renametablefield",
        {
            "INPUT": kozui_max_sum,
            "FIELD": "depth_max_sum",
            "NEW_NAME": constants.field_kozui,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
        feedback=f,
    )["OUTPUT"]

    # populate null values with 0
    seamless_sql = f'CASE WHEN "{constants.field_kozui}" > 0'
    seamless_sql += f' THEN "{constants.field_kozui}" ELSE 0 END'
    kozui_mesh = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": kozui_renamed,
            "FIELD_NAME": constants.field_kozui,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": seamless_sql,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    inland_calculated_mesh = _adjust_inland_score(kozui_mesh, constants.field_kozui)

    # remove temporary layers
    tmp_point_cliped_lyr = QgsProject.instance().mapLayersByName("tmp_point_cliped")[0]
    QgsProject.instance().removeMapLayer(tmp_point_cliped_lyr.id())

    return inland_calculated_mesh


def seamless2hmg_jisuberi(
    jisuberi_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    jisuberi_clipped = _clip_with_valid_geometries(jisuberi_lyr, waku_lyr)

    # Handle when there is no cliped features
    if jisuberi_clipped.featureCount() == 0:
        jisuberi_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_jisuberi)
        return jisuberi_mesh

    add_to_map(jisuberi_clipped, f"seamless_{constants.field_jisuberi}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        jisuberi_clipped, mesh_lyr, constants.field_jisuberi
    )
    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_jisuberi
    )

    return inland_calculated_mesh


def seamless2hmg_saigai(
    saigai_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    saigai_clipped = _clip_with_valid_geometries(saigai_lyr, waku_lyr)

    # Handle when there is no cliped features
    if saigai_clipped.featureCount() == 0:
        saigai_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_saigai)
        return saigai_mesh

    add_to_map(saigai_clipped, f"seamless_{constants.field_saigai}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        saigai_clipped, mesh_lyr, constants.field_saigai
    )
    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_saigai
    )

    return inland_calculated_mesh


def seamless2hmg_tornado(
    tornado_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    tornado_clipped = _clip_with_valid_geometries(tornado_lyr, waku_lyr)

    # Handle when there is no cliped features
    if tornado_clipped.featureCount() == 0:
        tornado_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_tornado)
        return tornado_mesh

    add_to_map(tornado_clipped, f"seamless_{constants.field_tornado}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        tornado_clipped, mesh_lyr, constants.field_tornado
    )

    return sum_surface_mesh


def seamless2hmg_sediments(
    sediments_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    sediments_clipped = _clip_with_valid_geometries(sediments_lyr, waku_lyr)

    # Handle when there is no cliped features
    if sediments_clipped.featureCount() == 0:
        sediments_mesh = _handle_zero_polygon_hazard(
            mesh_lyr, constants.field_sediments
        )
        return sediments_mesh

    add_to_map(sediments_clipped, f"seamless_{constants.field_sediments}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        sediments_clipped, mesh_lyr, constants.field_sediments
    )
    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_sediments
    )

    return inland_calculated_mesh


def _make_tsunami_rank_sql() -> str:
    height = "A40_003"
    sql = "CASE "
    sql += f"WHEN \"{height}\" = '～ 0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.01m以上 ～ 0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.01m以上 0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.01m以上～0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.3m以上 ～ 0.5m未満' THEN 0.4 "
    sql += f"WHEN \"{height}\" = '0.3m以上 0.5m未満' THEN 0.4 "
    sql += f"WHEN \"{height}\" = '0.3m以上 ～ 1m未満' THEN 0.6 "
    sql += f"WHEN \"{height}\" = '0.3m以上～1m未満' THEN 0.6 "
    sql += f"WHEN \"{height}\" = '0.5m以上 ～ 1m未満' THEN 0.7 "
    sql += f"WHEN \"{height}\" = '0.5m以上 1.0m未満' THEN 0.7 "
    sql += f"WHEN \"{height}\" = '1m以上 ～ 2m未満' THEN 1.5 "
    sql += f"WHEN \"{height}\" = '1m以上～2m未満' THEN 1.5 "
    sql += f"WHEN \"{height}\" = '1.0m以上 3.0m未満' THEN 2 "
    sql += f"WHEN \"{height}\" = '1m以上 ～ 3m未満' THEN 2 "
    sql += f"WHEN \"{height}\" = '2m以上 ～ 3m未満' THEN 2.5 "
    sql += f"WHEN \"{height}\" = '2m以上～3m未満' THEN 2.5 "
    sql += f"WHEN \"{height}\" = '2m以上 ～ 4m未満' THEN 3 "
    sql += f"WHEN \"{height}\" = '2m以上 ～ 5m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3m以上 ～ 4m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3m以上～4m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3.0m以上 5.0m未満' THEN 4 "
    sql += f"WHEN \"{height}\" = '3m以上 ～ 5m未満' THEN 4 "
    sql += f"WHEN \"{height}\" = '4m以上 ～ 5m未満' THEN 4.5 "
    sql += f"WHEN \"{height}\" = '4m以上～5m未満' THEN 4.5 "
    sql += f"WHEN \"{height}\" = '4m以上' THEN 6 "
    sql += f"WHEN \"{height}\" = '5.0m以上 10.0m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '5m以上' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '5m以上 ～ 10m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '5m以上～10m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '10m以上 ～ 15m未満' THEN 12.5 "
    sql += f"WHEN \"{height}\" = '10.0m以上 20.0m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '10m以上' THEN 15 "
    sql += f"WHEN \"{height}\" = '10m以上 ～ 20m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '10m以上～20m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '15m以上 ～ 20m未満' THEN 17.5 "
    sql += f"WHEN \"{height}\" = '20.0m以上' THEN 30 "
    sql += f"WHEN \"{height}\" = '20m以上' THEN 30 "
    sql += f"WHEN \"{height}\" = '20m以上 ～ 50m未満' THEN 35 "
    sql += f"WHEN \"{height}\" = '〜 0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.01m以上 〜 0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.01m以上〜0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.3m以上 〜 0.5m未満' THEN 0.4 "
    sql += f"WHEN \"{height}\" = '0.3m以上 〜 1m未満' THEN 0.6 "
    sql += f"WHEN \"{height}\" = '0.3m以上〜1m未満' THEN 0.6 "
    sql += f"WHEN \"{height}\" = '0.5m以上 〜 1m未満' THEN 0.7 "
    sql += f"WHEN \"{height}\" = '1m以上 〜 2m未満' THEN 1.5 "
    sql += f"WHEN \"{height}\" = '1m以上〜2m未満' THEN 1.5 "
    sql += f"WHEN \"{height}\" = '1m以上 〜 3m未満' THEN 2 "
    sql += f"WHEN \"{height}\" = '2m以上 〜 3m未満' THEN 2.5 "
    sql += f"WHEN \"{height}\" = '2m以上〜3m未満' THEN 2.5 "
    sql += f"WHEN \"{height}\" = '2m以上 〜 4m未満' THEN 3 "
    sql += f"WHEN \"{height}\" = '2m以上 〜 5m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3m以上 〜 4m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3m以上〜4m未満' THEN 3.5 "
    sql += f"WHEN \"{height}\" = '3m以上 〜 5m未満' THEN 4 "
    sql += f"WHEN \"{height}\" = '4m以上 〜 5m未満' THEN 4.5 "
    sql += f"WHEN \"{height}\" = '4m以上〜5m未満' THEN 4.5 "
    sql += f"WHEN \"{height}\" = '5m以上 〜 10m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '5m以上〜10m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '10m以上 〜 15m未満' THEN 12.5 "
    sql += f"WHEN \"{height}\" = '10m以上 〜 20m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '10m以上〜20m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '15m以上 〜 20m未満' THEN 17.5 "
    sql += f"WHEN \"{height}\" = '20m以上 〜 50m未満' THEN 35 "
    sql += "ELSE 0 END"
    return sql


def seamless2hmg_tsunami(
    tsunami_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    tsunami_clipped = _clip_with_valid_geometries(tsunami_lyr, waku_lyr)

    # Handle when there is no cliped features
    if tsunami_clipped.featureCount() == 0:
        tsunami_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_tsunami)
        return tsunami_mesh

    # calculate tsunami rank according to height
    tsunami_ranked = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": tsunami_clipped,
            "FIELD_NAME": "h_tsunami",
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": _make_tsunami_rank_sql(),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(tsunami_ranked, f"seamless_{constants.field_tsunami}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        tsunami_ranked, mesh_lyr, constants.field_tsunami
    )

    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_tsunami
    )

    return inland_calculated_mesh


def _make_storm_surge_rank_sql() -> str:
    height = "A49_003"
    sql = "CASE "
    sql += f"WHEN \"{height}\" = '0.3m未満' THEN 0.1 "
    sql += f"WHEN \"{height}\" = '0.5m未満' THEN 0.2 "  # TBC
    sql += f"WHEN \"{height}\" = '0.3m以上0.5m未満' THEN 0.4 "
    sql += f"WHEN \"{height}\" = '0.5m以上1m未満' THEN 0.7 "
    sql += f"WHEN \"{height}\" = '0.5m以上3m未満' THEN 2 "  # TBC
    sql += f"WHEN \"{height}\" = '1m以上3m未満' THEN 2 "
    sql += f"WHEN \"{height}\" = '3m以上5m未満' THEN 4 "
    sql += f"WHEN \"{height}\" = '5m以上10m未満' THEN 7.5 "
    sql += f"WHEN \"{height}\" = '10m以上20m未満' THEN 15 "
    sql += f"WHEN \"{height}\" = '20m以上' THEN 30 "

    sql += "ELSE 0 END"
    return sql


def seamless2hmg_surge(
    surge_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    surge_clipped = _clip_with_valid_geometries(surge_lyr, waku_lyr)

    # Handle when there is no cliped features
    if surge_clipped.featureCount() == 0:
        surge_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_surge)
        return surge_mesh

    # calculate surge rank according to height
    surge_ranked = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": surge_clipped,
            "FIELD_NAME": "h_surge",
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": _make_storm_surge_rank_sql(),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(surge_ranked, f"seamless_{constants.field_surge}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        surge_ranked, mesh_lyr, constants.field_surge
    )

    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_surge
    )

    return inland_calculated_mesh
