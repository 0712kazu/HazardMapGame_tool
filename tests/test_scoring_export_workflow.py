from pathlib import Path

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
    QgsWkbTypes,
)

from output.game_data_exporter import GAME_FIELDS, export_game_data
from scoring.qgis_layer import calculate_layer_scores


def _square(x):
    return QgsGeometry.fromPolygonXY(
        [
            [
                QgsPointXY(x, 0),
                QgsPointXY(x + 100, 0),
                QgsPointXY(x + 100, 100),
                QgsPointXY(x, 100),
                QgsPointXY(x, 0),
            ]
        ]
    )


def _scoring_layer():
    layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "mesh_score", "memory")
    layer.dataProvider().addAttributes(
        [
            QgsField("id", QMetaType.Type.Int),
            QgsField("land_rate", QMetaType.Type.Double),
            QgsField("t_flood", QMetaType.Type.Int),
            QgsField("t_sediment", QMetaType.Type.Int),
            QgsField("t_slope", QMetaType.Type.Int),
            QgsField("t_tsunami", QMetaType.Type.Int),
        ]
    )
    layer.updateFields()
    rows = [
        (1, 0.11, 0, 0, 0, 0),
        (2, 0.50, 1, 1, 0, 1),
        (3, 1.00, 3, 0, 4, 2),
        (4, 0.75, 6, 6, 6, 6),
    ]
    features = []
    for index, row in enumerate(rows):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(_square(index * 100))
        feature.setAttributes(list(row))
        features.append(feature)
    success, _ = layer.dataProvider().addFeatures(features)
    assert success
    return layer


def test_scoring_recalculation_and_game_export_are_consistent(tmp_path):
    layer = _scoring_layer()

    initial = calculate_layer_scores(layer)
    initial_rows = list(layer.getFeatures())
    initial_non_flood = [
        (feature["t_sediment"], feature["t_slope"], feature["t_tsunami"])
        for feature in initial_rows
    ]

    assert initial.maximum_a33 == 6
    # 既に目標15点を超える場合は縮小せず、16点以上を許容する。
    assert initial.maximum_hzd == 18
    assert initial_rows[0]["HZD"] == 0
    assert initial.score_summary.fields["HZD"].zero_count == 1

    assert layer.startEditing()
    flood_index = layer.fields().indexFromName("t_flood")
    assert layer.changeAttributeValue(initial_rows[1].id(), flood_index, 4)
    assert layer.commitChanges()

    recalculated = calculate_layer_scores(
        layer, hzd_multiplier=initial.hzd_multiplier
    )
    recalculated_rows = list(layer.getFeatures())

    assert recalculated.hzd_multiplier == initial.hzd_multiplier
    assert [
        (feature["t_sediment"], feature["t_slope"], feature["t_tsunami"])
        for feature in recalculated_rows
    ] == initial_non_flood
    assert recalculated_rows[0]["HZD"] == 0

    result = export_game_data(layer, str(tmp_path), "通し検証")
    assert Path(result.processing_gpkg_path).exists()
    assert Path(result.game_geojson_path).exists()

    game_layer = QgsVectorLayer(result.game_geojson_path, "game", "ogr")
    assert game_layer.isValid()
    assert game_layer.featureCount() == 4
    assert tuple(game_layer.fields().names()) == GAME_FIELDS
    assert QgsWkbTypes.isMultiType(game_layer.wkbType())
    assert game_layer.crs().authid() == "EPSG:4326"
