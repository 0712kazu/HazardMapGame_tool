import pytest
from qgis.core import QgsFeature, QgsVectorLayer

from scoring.qgis_layer import LayerScoringError, calculate_layer_scores


def _mesh_layer(rows):
    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:3857"
        "&field=t_flood:integer"
        "&field=t_sediment:integer"
        "&field=t_slope:integer"
        "&field=t_tsunami:integer",
        "mesh_score",
        "memory",
    )
    features = []
    for row in rows:
        feature = QgsFeature(layer.fields())
        feature.setAttributes(row)
        features.append(feature)
    success, _ = layer.dataProvider().addFeatures(features)
    assert success
    return layer


def test_scores_are_written_to_the_layer():
    layer = _mesh_layer([[0, 0, 0, 0], [2, 6, 6, 1]])

    result = calculate_layer_scores(layer, hzd_multiplier=2)

    rows = list(layer.getFeatures())
    assert [row["A31"] for row in rows] == [0, 2]
    assert [row["A33"] for row in rows] == [0, 6]
    assert [row["A40"] for row in rows] == [0, 1]
    assert [row["base_hzd"] for row in rows] == [0, 9]
    assert [row["HZD"] for row in rows] == [0, 18]
    assert [row["hzd_multiplier"] for row in rows] == [2.0, 2.0]
    assert result.maximum_hzd == 18
    assert result.sediment_slope_overlap_count == 1


def test_recalculation_uses_the_passed_multiplier():
    layer = _mesh_layer([[1, 1, 0, 1]])
    first = calculate_layer_scores(layer, hzd_multiplier=2.5)

    assert layer.startEditing()
    feature = next(layer.getFeatures())
    assert layer.changeAttributeValue(
        feature.id(), layer.fields().indexFromName("t_flood"), 2
    )
    assert layer.commitChanges()

    second = calculate_layer_scores(
        layer, hzd_multiplier=first.hzd_multiplier
    )

    assert second.hzd_multiplier == 2.5
    assert next(layer.getFeatures())["HZD"] == 10


def test_missing_input_field_is_reported():
    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:3857&field=t_flood:integer",
        "mesh_score",
        "memory",
    )
    feature = QgsFeature(layer.fields())
    feature.setAttributes([1])
    success, _ = layer.dataProvider().addFeatures([feature])
    assert success

    with pytest.raises(LayerScoringError, match="t_sediment"):
        calculate_layer_scores(layer)
