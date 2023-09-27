import processing
from PyQt5.QtWidgets import QProgressBar
from qgis.core import (
    QgsFeatureRequest,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgisInterface


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
):
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

    kozui_cliped = processing.run(
        "native:clip",
        {
            "INPUT": QgsProcessingFeatureSourceDefinition(
                kozui_lyr.source(),
                selectedFeaturesOnly=False,
                featureLimit=-1,
                flags=QgsProcessingFeatureSourceDefinition.FlagOverrideDefaultGeometryCheck,
                geometryCheck=QgsFeatureRequest.GeometryNoCheck,
            ),
            "OVERLAY": waku_lyr,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    QgsProject.instance().addMapLayer(kozui_cliped)

    # 標準化
    kozui_standard = processing.run(
        "qgis:executesql",
        {
            "INPUT_DATASOURCES": [kozui_cliped],
            "INPUT_QUERY": _make_depth_sql(kozui_cliped),
            "INPUT_UID_FIELD": "",
            "INPUT_GEOMETRY_FIELD": "",
            "INPUT_GEOMETRY_TYPE": None,
            "INPUT_GEOMETRY_CRS": None,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    QgsProject.instance().addMapLayer(kozui_standard)

    # 20m間隔ポイントを作成
    pnt_lyr = processing.run(
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
    for lyr in [kozui_standard, pnt_lyr, mesh_lyr]:
        processing.run("native:createspatialindex", {"INPUT": lyr})

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
    QgsProject.instance().addMapLayer(max_dep_pnt)

    print("メッシュごとの最大浸水深合計を計算...")
    kosui_sum_mesh = processing.run(
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

    QgsProject.instance().addMapLayer(kosui_sum_mesh)
