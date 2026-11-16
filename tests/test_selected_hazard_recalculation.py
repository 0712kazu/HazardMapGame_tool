from qgis.core import QgsFeature, QgsVectorLayer

from ui.main_window import MainWindow


def _layer_with_existing_scores():
    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:3857"
        "&field=flood:double"
        "&field=sediment:double"
        "&field=slope:double"
        "&field=tsunami:double"
        "&field=t_flood:integer"
        "&field=t_sediment:integer"
        "&field=t_slope:integer"
        "&field=t_tsunami:integer",
        "mesh_score",
        "memory",
    )
    rows = [
        [0, 10, 20, 30, 6, 5, 4, 3],
        [100, 20, 30, 40, 6, 5, 4, 3],
    ]
    features = []
    for row in rows:
        feature = QgsFeature(layer.fields())
        feature.setAttributes(row)
        features.append(feature)
    success, _ = layer.dataProvider().addFeatures(features)
    assert success
    return layer


def test_recalculation_target_selector_is_available():
    window = MainWindow()
    selector = window.hmg_data_classifier.recalculation_target

    assert [selector.itemData(index) for index in range(selector.count())] == [
        "all",
        "kozui",
        "sediments",
        "slope",
        "tsunami",
    ]


def test_only_selected_hazard_rank_is_recalculated():
    window = MainWindow()
    classifier = window.hmg_data_classifier
    layer = _layer_with_existing_scores()

    updated = classifier._calculate_ui_score(layer, "", ["kozui"])
    rows = list(layer.getFeatures())

    assert updated == ["t_flood"]
    assert [row["t_flood"] for row in rows] == [0, 5]
    assert [row["t_sediment"] for row in rows] == [5, 5]
    assert [row["t_slope"] for row in rows] == [4, 4]
    assert [row["t_tsunami"] for row in rows] == [3, 3]
