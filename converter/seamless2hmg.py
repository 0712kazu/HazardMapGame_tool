import processing
from qgis.PyQt.QtWidgets import QProgressBar, QMessageBox
from qgis.core import (
    NULL,
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgisInterface

from qgis.core import QgsProcessingFeatureSourceDefinition as qpfsd

import constants
from converter.inundation_categories import (
    FLOOD_V1_DEPTHS,
    FLOOD_V1_FIELDS,
    FLOOD_V2_DEPTHS,
    FLOOD_V2_FIELDS,
    STORM_SURGE_DEPTHS,
    TSUNAMI_DEPTHS,
    validate_categories,
)
from hmg_utils import add_to_map, remove_layer


def _validate_layer_categories(layer, hazard_name, field_name, allowed_values):
    if layer.fields().lookupField(field_name) == -1:
        raise ValueError(
            f"{hazard_name}の浸水区分フィールド「{field_name}」が見つかりません。"
        )
    values = (
        None if feature[field_name] == NULL else feature[field_name]
        for feature in layer.getFeatures()
    )
    validate_categories(
        hazard_name,
        field_name,
        values,
        allowed_values,
    )


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
                geometryCheck=QgsFeatureRequest.GeometrySkipInvalid,
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
    message = f"対象領域にポリゴンが存在しないため「{target_field}」の値が0になります。"
    QMessageBox.information(None, "お知らせ", message)
    return mesh_calculated


def _sum_surfaces_intersect_meshes(
    seamless_lyr: QgsVectorLayer,
    mesh_lyr: QgsVectorLayer,
    calculate_field: str,
    value_field="",
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
    # value_field is used to multiply with surface
    if value_field != "":
        dissolve_field = [value_field]

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

    # value_field is used to multiply with surface when defined
    if value_field != "":
        area_formula = f" area(@geometry) * {value_field}"

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


def _mean_mesh_centroid_values(
    seamless_lyr: QgsVectorLayer,
    seamless_field: str,
    mesh_lyr: QgsVectorLayer,
    calculate_field: str,
) -> QgsVectorLayer:
    # reproject to 3857
    seamless_reprojected = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": seamless_lyr,
            "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:3857"),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # make centroids of clipped seamless
    seamless_centroids = processing.run(
        "native:pointonsurface",
        {
            "INPUT": seamless_reprojected,
            "ALL_PARTS": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    # For slope, erase centroids in sediments 土砂
    if (
        calculate_field == constants.field_slope
        and QgsProject.instance().mapLayersByName(
            f"seamless_{constants.field_sediments}"
        )
    ):
        sediments_layer = QgsProject.instance().mapLayersByName(
            f"seamless_{constants.field_sediments}"
        )[0]
        seamless_filtered = processing.run(
            "native:difference",
            {
                "INPUT": seamless_centroids,
                "OVERLAY": sediments_layer,
                "OUTPUT": "TEMPORARY_OUTPUT",
                "GRID_SIZE": None,
            },
        )["OUTPUT"]
        seamless_centroids = seamless_filtered

    # intersect with mesh
    centroids_mesh_intersect = processing.run(
        "native:intersection",
        {
            "INPUT": seamless_centroids,
            "OVERLAY": mesh_lyr,
            "INPUT_FIELDS": [seamless_field],
            "OVERLAY_FIELDS": ["id"],
            "OVERLAY_FIELDS_PREFIX": "mesh_",
            "OUTPUT": "TEMPORARY_OUTPUT",
            "GRID_SIZE": None,
        },
    )["OUTPUT"]

    # aggregate mean value for each mesh id
    centroids_mean_by_mesh = processing.run(
        "native:aggregate",
        {
            "INPUT": centroids_mesh_intersect,
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
                    "aggregate": "mean",
                    "delimiter": ",",
                    "input": f'"{seamless_field}"',
                    "length": 0,
                    "name": f"{calculate_field}",
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
    mesh_join_seamless_mean = processing.run(
        "native:joinattributestable",
        {
            "INPUT": mesh_lyr,
            "FIELD": "id",
            "INPUT_2": centroids_mean_by_mesh,
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
    seamless_centroid_mean_mesh = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": mesh_join_seamless_mean,
            "FIELD_NAME": calculate_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": seamless_sql,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    return seamless_centroid_mean_mesh


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
    depth_sql = "SELECT geometry, CASE "
    supported_field_found = False
    present_fields = []

    for field in FLOOD_V1_FIELDS:
        if kozui_layer.fields().lookupField(field) != -1:
            supported_field_found = True
            present_fields.append(field)
            _validate_layer_categories(
                kozui_layer, "洪水", field, FLOOD_V1_DEPTHS.keys()
            )
            for category, depth in FLOOD_V1_DEPTHS.items():
                depth_sql += f"WHEN {field} = {category} THEN {depth} "

    for field in FLOOD_V2_FIELDS:
        if kozui_layer.fields().lookupField(field) != -1:
            supported_field_found = True
            present_fields.append(field)
            _validate_layer_categories(
                kozui_layer, "洪水", field, FLOOD_V2_DEPTHS.keys()
            )
            for category, depth in FLOOD_V2_DEPTHS.items():
                depth_sql += f"WHEN {field} = {category} THEN {depth} "

    if not supported_field_found:
        raise ValueError("洪水の浸水区分フィールドが見つかりません。")

    # 複数の区分フィールドがある場合、他フィールドの有効値を先に採用する。
    # すべての既知区分を判定した後でのみ、明示的な0を0として扱う。
    for field in present_fields:
        depth_sql += f"WHEN {field} = 0 THEN 0 "

    depth_sql += "ELSE NULL END AS depth "
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
                geometryCheck=QgsFeatureRequest.GeometrySkipInvalid,
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

    add_to_map(kozui_cliped_fixed, f"tmp_clipped_{constants.field_kozui}")

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

    add_to_map(kozui_standard, f"seamless_{constants.field_kozui}")

    # 20m間隔ポイントを作成
    pnt_lyr_raw = processing.run(
        "native:creategrid",
        {
            "TYPE": 0,
            "EXTENT": waku_lyr.extent(),
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

    # Get only points intersects flood polygons to improve speed
    try:
        pnt_lyr = processing.run(
            "native:clip",
            {
                "INPUT": pnt_lyr_raw,
                "OVERLAY": kozui_cliped_fixed,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

        processing.run("native:createspatialindex", {"INPUT": pnt_lyr})

    except Exception as e:
        # When "Could not create the combined clip geometry" error occurs skip it
        print(f"pnt clip error: {e}")
        pnt_lyr = pnt_lyr_raw

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
    remove_layer("tmp_point_cliped")
    remove_layer(f"tmp_clipped_{constants.field_kozui}")

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
    sql += f'WHEN "{height}" IS NULL THEN 0 '
    sql += f'WHEN "{height}" IN (0, \'0\', \'0.0\') THEN 0 '
    for category, depth in TSUNAMI_DEPTHS.items():
        sql += f'WHEN "{height}" = \'{category}\' THEN {depth} '
    sql += "ELSE NULL END"
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

    _validate_layer_categories(
        tsunami_clipped, "津波", "A40_003", TSUNAMI_DEPTHS.keys()
    )

    # calculate tsunami rank according to height
    tsunami_value_field = "h_tsunami"
    tsunami_ranked = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": tsunami_clipped,
            "FIELD_NAME": tsunami_value_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": _make_tsunami_rank_sql(),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(tsunami_ranked, f"seamless_{constants.field_tsunami}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        tsunami_ranked, mesh_lyr, constants.field_tsunami, tsunami_value_field
    )

    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_tsunami
    )

    return inland_calculated_mesh


def _make_storm_surge_rank_sql() -> str:
    height = "A49_003"
    sql = "CASE "
    sql += f'WHEN "{height}" IS NULL THEN 0 '
    sql += f'WHEN "{height}" IN (0, \'0\', \'0.0\') THEN 0 '
    for category, depth in STORM_SURGE_DEPTHS.items():
        sql += f'WHEN "{height}" = \'{category}\' THEN {depth} '
    sql += "ELSE NULL END"
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

    _validate_layer_categories(
        surge_clipped, "高潮", "A49_003", STORM_SURGE_DEPTHS.keys()
    )

    # calculate surge rank according to height
    surge_value_field = "h_surge"
    surge_ranked = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": surge_clipped,
            "FIELD_NAME": surge_value_field,
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": _make_storm_surge_rank_sql(),
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(surge_ranked, f"seamless_{constants.field_surge}")

    sum_surface_mesh = _sum_surfaces_intersect_meshes(
        surge_ranked, mesh_lyr, constants.field_surge, surge_value_field
    )

    inland_calculated_mesh = _adjust_inland_score(
        sum_surface_mesh, constants.field_surge
    )

    return inland_calculated_mesh


def seamless2hmg_earthquake(
    earthquake_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    earthquake_clipped = _clip_with_valid_geometries(earthquake_lyr, waku_lyr)

    # Handle when there is no cliped features
    if earthquake_clipped.featureCount() == 0:
        earthquake_mesh = _handle_zero_polygon_hazard(
            mesh_lyr, constants.field_earthquake
        )
        return earthquake_mesh

    add_to_map(earthquake_clipped, f"seamless_{constants.field_earthquake}")

    mean_centroids_mesh = _mean_mesh_centroid_values(
        earthquake_clipped, "T30_I60_PS", mesh_lyr, constants.field_earthquake
    )

    return mean_centroids_mesh


def seamless2hmg_slope(
    slope_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    slope_clipped = _clip_with_valid_geometries(slope_lyr, waku_lyr)

    # Handle when there is no cliped features
    if slope_clipped.featureCount() == 0:
        slope_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_slope)
        return slope_mesh

    # get only numeric values
    slope_filtered = processing.run(
        "native:fieldcalculator",
        {
            "INPUT": slope_clipped,
            "FIELD_NAME": "angle",
            "FIELD_TYPE": 0,
            "FIELD_LENGTH": 0,
            "FIELD_PRECISION": 0,
            "FORMULA": ' "G04d_010" ',
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    add_to_map(slope_filtered, f"seamless_{constants.field_slope}")

    mean_centroids_mesh = _mean_mesh_centroid_values(
        slope_filtered, "angle", mesh_lyr, constants.field_slope
    )

    return mean_centroids_mesh


def seamless2hmg_refuge(
    refuge_lyr: QgsVectorLayer, mesh_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    refuge_clipped = _clip_with_valid_geometries(refuge_lyr, waku_lyr)

    # Handle when there is no cliped features
    if refuge_clipped.featureCount() == 0:
        refuge_mesh = _handle_zero_polygon_hazard(mesh_lyr, constants.field_refuge)
        return refuge_mesh

    add_to_map(refuge_clipped, f"seamless_{constants.field_refuge}")

    mesh_count_refuge = processing.run(
        "native:countpointsinpolygon",
        {
            "POLYGONS": mesh_lyr,
            "POINTS": refuge_clipped,
            "WEIGHT": "",
            "CLASSFIELD": "",
            "FIELD": constants.field_refuge,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    return mesh_count_refuge


def seamless2hmg_custom(
    custom_lyr: QgsVectorLayer,
    mesh_lyr: QgsVectorLayer,
    waku_lyr: QgsVectorLayer,
    custom_field: str,
    calc_method: str,
    seamless_field: str,
    adjust_inland_score_option: bool,
) -> QgsVectorLayer:
    # extract intersected polygons to avoid clip intersect error
    custom_clipped = _clip_with_valid_geometries(custom_lyr, waku_lyr)

    # Handle when there is no cliped features
    if custom_clipped.featureCount() == 0:
        custom_mesh = _handle_zero_polygon_hazard(mesh_lyr, custom_field)
        return custom_mesh

    add_to_map(custom_clipped, f"seamless_{custom_field}")

    custom_geom_type = custom_clipped.geometryType()

    # sum surfaces
    if calc_method == "sum_surfaces":
        if custom_geom_type != QgsWkbTypes.PolygonGeometry:
            error_message = "エラーが発生しました。\n\n"
            error_message += "追加災害のレイヤはポリゴンではありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        mesh_custom = _sum_surfaces_intersect_meshes(
            custom_clipped, mesh_lyr, custom_field
        )

    # csum surfaces x values
    if calc_method == "sum_surfaces_values":
        if custom_geom_type != QgsWkbTypes.PolygonGeometry:
            error_message = "エラーが発生しました。\n\n"
            error_message += "追加災害のレイヤはポリゴンではありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        # check if seamless_field is exists and if it is numeric
        field_index = custom_lyr.fields().indexFromName(seamless_field)
        if field_index == -1:
            error_message = "エラーが発生しました。\n\n"
            error_message += f"シームレスレイヤに「{seamless_field}」属性がありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        if not custom_lyr.fields()[field_index].isNumeric():
            error_message = "エラーが発生しました。\n\n"
            error_message += (
                f"シームレスレイヤの「{seamless_field}」属性に"
                "数値以外のデータが含まれています。"
            )
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        mesh_custom = _sum_surfaces_intersect_meshes(
            custom_clipped, mesh_lyr, custom_field, seamless_field
        )

    # centroid value means
    if calc_method == "centroid_value_mean":
        if custom_geom_type != QgsWkbTypes.PolygonGeometry:
            error_message = "エラーが発生しました。\n\n"
            error_message += "追加災害のレイヤはポリゴンではありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        if seamless_field == "":
            error_message = "エラーが発生しました。\n\n"
            error_message += "シームレス値属性名を指定してください。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        # check if seamless_field is exists and if it is numeric
        field_index = custom_lyr.fields().indexFromName(seamless_field)
        if field_index == -1:
            error_message = "エラーが発生しました。\n\n"
            error_message += f"シームレスレイヤに「{seamless_field}」属性がありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        if not custom_lyr.fields()[field_index].isNumeric():
            error_message = "エラーが発生しました。\n\n"
            error_message += (
                f"シームレスレイヤの「{seamless_field}」属性に"
                "数値以外のデータが含まれています。"
            )
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        mesh_custom = _mean_mesh_centroid_values(
            custom_clipped, seamless_field, mesh_lyr, custom_field
        )

    # count points in meshes
    if calc_method == "count_points":
        if custom_geom_type != QgsWkbTypes.PointGeometry:
            error_message = "エラーが発生しました。\n\n"
            error_message += "追加災害のレイヤはポイントではありません。"
            QMessageBox.information(None, "エラー", error_message)
            return mesh_lyr

        mesh_custom = processing.run(
            "native:countpointsinpolygon",
            {
                "POLYGONS": mesh_lyr,
                "POINTS": custom_clipped,
                "WEIGHT": "",
                "CLASSFIELD": "",
                "FIELD": custom_field,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

    if adjust_inland_score_option:
        mesh_custom = _adjust_inland_score(mesh_custom, custom_field)

    return mesh_custom


def seamless2hmg_landuse(landuse_lyr: QgsVectorLayer, waku_lyr: QgsVectorLayer) -> None:
    # clip seamless data only and add to map
    landuse_clipped = _clip_with_valid_geometries(landuse_lyr, waku_lyr)

    add_to_map(landuse_clipped, f"seamless_{constants.field_landuse}")
