from qgis.core import (
    QgsVectorLayer,
    QgsGraduatedSymbolRenderer,
    QgsClassificationRange,
    QgsFillSymbol,
    QgsRendererRange,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsField,
    QgsFeatureRequest,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QFont

import constants
from scoring.classification import (
    classify_standard_deviation_ranks,
    classify_tcg_ranks,
    ranks_to_percentages,
)


def _get_round_precision(value: float) -> int:
    if value < constants.MAP_MIN_VALUE:
        return 4
    elif value < 0.01:
        return 3
    elif value < 0.1:
        return 2
    else:
        return 1


def graduate_layer(layer: QgsVectorLayer, target_field: str, breaks: list):
    # Set the symbol layer to the renderer
    # breaks list format = [[0, 1000, "#FFFFFF"], [1001, 9999999999, "#0000FF"]]

    renderer = QgsGraduatedSymbolRenderer(target_field)

    # get minimum value to calculate round
    all_breaks = [
        item
        for element in breaks
        for item in element
        if isinstance(item, (int, float)) and item > constants.MAP_MIN_VALUE
    ]
    if all_breaks:
        min_break = min(all_breaks)
        label_precision = _get_round_precision(min_break)
    else:
        label_precision = 0

    for vmin, vmax, color in breaks:
        # skip if it is 0,0 break
        if vmin == 0 and vmax == 0:
            continue
        if vmin < constants.MAP_MIN_VALUE and color != "transparent":
            vmin = constants.MAP_MIN_VALUE
            label_min = constants.MAP_MIN_VALUE
        else:
            label_min = round(vmin, label_precision)

        if vmax < constants.MAP_MIN_VALUE:
            vmax = constants.MAP_MIN_VALUE
            label_max = constants.MAP_MIN_VALUE
        else:
            label_max = round(vmax, label_precision)

        classificationRange = QgsClassificationRange(
            f"{label_min} < {target_field} <= {label_max}", vmin, vmax
        )
        if color == "transparent":
            color_txt = "0,0,0,0"
            classificationRange = QgsClassificationRange(
                f"{target_field} <= {constants.MAP_MIN_VALUE}", vmin, vmax
            )
        else:
            # convert #FFFFFF to "255,255,255,135"
            # with opacity as 200 value
            hex_color = color.lstrip("#")
            rgb = tuple(int(hex_color[i] + hex_color[i + 1], 16) for i in (0, 2, 4))
            rgbtext = ", ".join(map(str, rgb))
            color_txt = rgbtext + ", 200"
        properties = {
            "color": color_txt,
            "outline_color": "black",
            "outline_width": 0.1,
        }

        symbol = QgsFillSymbol.createSimple(properties)
        rendererRange = QgsRendererRange(classificationRange, symbol)
        renderer.addClassRange(rendererRange)

    layer.setRenderer(renderer)

    # Add labels for values >= minimum
    # Create label settings
    label_settings = QgsPalLayerSettings()
    expression = (
        f'CASE WHEN "{target_field}" >= {constants.MAP_MIN_VALUE}'
        f" THEN ROUND(\"{target_field}\",{label_precision}) ELSE '' END"
    )
    label_settings.fieldName = expression
    label_settings.isExpression = True

    # Set font properties
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial Narrow", 8))
    text_format.setSize(8)

    label_settings.setFormat(text_format)

    # Apply label settings to the layer
    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)

    layer.triggerRepaint()


def get_mesh_value_from_percentage(mesh_values: list, percent_value: float) -> float:
    mesh_rank = len(mesh_values) * percent_value / 100
    if round(mesh_rank) == 0:
        mesh_value = mesh_values[0]
    else:
        mesh_value = mesh_values[round(mesh_rank) - 1]

    return mesh_value


def classify_values_stdev(values: list, num_classes: int) -> list:
    """
    return classification in percentage values from given
    values sample and a specific number of classes
    input:
    - values [0,0,24,255,484,1056...]
    - num_classes: 6
    output:
    - class_percentages : [30,43,54,85,90,91,,100] a list of percentages
    - output has num_classes + 1 breaks to make num_classes breaks
    - percentage 0 is removed
    - duplicated percentages are removed
    """

    ranks = classify_standard_deviation_ranks(values, num_classes)
    return ranks_to_percentages(ranks, num_classes)


def classify_values_tcg(values: list, max_rank: int = 6) -> list:
    """get tcg classification as percentage"""
    tcg_classes = get_tcg_ranks(values, max_rank)
    return ranks_to_percentages(tcg_classes, max_rank)


def get_tcg_ranks(values: list, max_rank: int = 6) -> list:
    """Return a list of TCG rank associated to input values
    input :[0,10,255,3598,3699,8555]
    output with max_rank=6 : [0,1,1,2,3,5]
    """
    return classify_tcg_ranks(values, max_rank)


def calculate_tcg_score(
    mesh_score_layer: QgsVectorLayer, custom_field_name: str
) -> list:
    # list of added fields
    tcg_rank_fields_added = []
    for hazard in constants.hazards_ui_names:
        # get mesh_score target field name
        if hazard == "custom":
            target_field = custom_field_name
        else:
            target_field = getattr(constants, f"field_{hazard}")

        if target_field in mesh_score_layer.fields().names():
            field_values = [
                feature[target_field] for feature in mesh_score_layer.getFeatures()
            ]
            y_values = sorted(field_values)
        else:
            continue
        # get ranks from values
        tcg_ranks = get_tcg_ranks(y_values)
        tcg_rank_field = f"t_{target_field}"

        # add tcg rank field if not exists
        if tcg_rank_field not in mesh_score_layer.fields().names():
            mesh_score_layer.startEditing()
            mesh_score_layer.addAttribute(QgsField(tcg_rank_field, QVariant.Int))
            mesh_score_layer.commitChanges()

        # calculate tcg rank
        mesh_score_layer.startEditing()
        # input y_values to be in ascending order :[0,10,255,3598,3699,8555]
        # ranks are calculated from cumulative risk share
        # Sort the features based on hazard score ascending order
        request = QgsFeatureRequest().addOrderBy(target_field, ascending=True)
        features = mesh_score_layer.getFeatures(request)

        # Update the tcg rank field based on the sorting order
        for index, feature in enumerate(features):
            feature.setAttribute(tcg_rank_field, tcg_ranks[index])
            mesh_score_layer.updateFeature(feature)

        # Stop editing and save changes
        mesh_score_layer.commitChanges()

        tcg_rank_fields_added.append(tcg_rank_field)
    return tcg_rank_fields_added


def get_color_from_range(break_id: int, nb_breaks: int) -> str:
    if nb_breaks == 1:
        color = "#fddbc7"
    elif nb_breaks == 2:
        color = {
            1: "#0571b0",
            2: "#ca0020",
        }.get(break_id, "#00000")
    elif nb_breaks == 3:
        color = {
            1: "#0571b0",
            2: "#f7f7f7",
            3: "#ca0020",
        }.get(break_id, "#00000")
    elif nb_breaks == 4:
        color = {
            1: "#0571b0",
            2: "#92c5de",
            3: "#f4a582",
            4: "#ca0020",
        }.get(break_id, "#00000")
    elif nb_breaks == 5:
        color = {
            1: "#0571b0",
            2: "#92c5de",
            3: "#f7f7f7",
            4: "#f4a582",
            5: "#ca0020",
        }.get(break_id, "#00000")
    elif nb_breaks == 6:
        color = {
            1: "#2166ac",
            2: "#67a9cf",
            3: "#d1e5f0",
            4: "#fddbc7",
            5: "#ef8a62",
            6: "#b2182b",
        }.get(break_id, "#00000")
    elif nb_breaks == 7:
        color = {
            1: "#053061",
            2: "#2166ac",
            3: "#4393c3",
            4: "#d1e5f0",
            5: "#f4a582",
            6: "#d6604d",
            7: "#67001f",
        }.get(break_id, "#00000")
    elif nb_breaks == 8:
        color = {
            1: "#053061",
            2: "#2166ac",
            3: "#4393c3",
            4: "#d1e5f0",
            5: "#f4a582",
            6: "#d6604d",
            7: "#b2182b",
            8: "#67001f",
        }.get(break_id, "#00000")
    elif nb_breaks == 9:
        color = {
            1: "#053061",
            2: "#2166ac",
            3: "#4393c3",
            4: "#92c5de",
            5: "#d1e5f0",
            6: "#f4a582",
            7: "#d6604d",
            8: "#b2182b",
            9: "#67001f",
        }.get(break_id, "#00000")
    elif nb_breaks == 10:
        color = {
            1: "#053061",
            2: "#2166ac",
            3: "#4393c3",
            4: "#92c5de",
            5: "#d1e5f0",
            6: "#fddbc7",
            7: "#f4a582",
            8: "#d6604d",
            9: "#b2182b",
            10: "#67001f",
        }.get(break_id, "#00000")
    elif nb_breaks == 11:
        color = {
            1: "#011730",
            2: "#053061",
            3: "#2166ac",
            4: "#4393c3",
            5: "#92c5de",
            6: "#d1e5f0",
            7: "#fddbc7",
            8: "#f4a582",
            9: "#d6604d",
            10: "#b2182b",
            11: "#67001f",
        }.get(break_id, "#00000")

    return color
