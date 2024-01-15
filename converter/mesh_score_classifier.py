from qgis.core import (
    QgsVectorLayer,
    QgsGraduatedSymbolRenderer,
    QgsClassificationRange,
    QgsFillSymbol,
    QgsRendererRange,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QFont

import numpy as np
import constants


def graduate_layer(layer: QgsVectorLayer, target_field: str, breaks: list):
    # Set the symbol layer to the renderer
    # breaks list format = [[0, 1000, "#FFFFFF"], [1001, 9999999999, "#0000FF"]]

    renderer = QgsGraduatedSymbolRenderer(target_field)

    for min, max, color in breaks:
        # skip if it is 0,0 break
        if min == 0 and max == 0:
            continue
        if min < constants.MAP_MIN_VALUE and color != "transparent":
            min = constants.MAP_MIN_VALUE
            label_min = constants.MAP_MIN_VALUE
        else:
            label_min = round(min, 1)
        if max < constants.MAP_MIN_VALUE:
            max = constants.MAP_MIN_VALUE
            label_max = constants.MAP_MIN_VALUE
        else:
            label_max = round(max, 1)

        classificationRange = QgsClassificationRange(
            f"{label_min} < {target_field} <= {label_max}", min, max
        )
        if color == "transparent":
            color_txt = "0,0,0,0"
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
        f" THEN ROUND(\"{target_field}\",1) ELSE '' END"
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
    - class_percentages : [0,54,85,90,100] a list of percentages
    -
    """

    # Calculate mean and standard deviation
    mean_value = np.mean(values)
    std_dev = np.std(values)

    # Calculate class width
    class_width = 2 * std_dev / num_classes

    # Calculate class boundaries
    class_boundaries = [
        mean_value - std_dev + i * class_width for i in range(1, num_classes)
    ]
    class_boundaries.append(mean_value + std_dev)  # Add the upper boundary

    # Classify values
    classes = np.digitize(values, class_boundaries)

    # Convert to total percentages
    class_percentages = []
    total_sample = 0
    for i in range(1, num_classes):
        nb_elements_in_class = classes.tolist().count(i)
        total_sample += nb_elements_in_class
        percentage = total_sample / len(values) * 100
        class_percentages.append(percentage)
    class_percentages.append(100)

    # remove duplicate values
    class_percentages = list(set(class_percentages))

    return sorted(class_percentages)


def classify_values_tcg(values: list) -> list:
    """get tcg classification as percentage"""
    tcg_classes = get_tcg_ranks(values)

    # Convert to total percentages
    class_percentages = []
    total_sample = 0
    for i in range(0, 6):
        nb_elements_in_class = tcg_classes.count(i)
        total_sample += nb_elements_in_class
        percentage = total_sample / len(values) * 100
        class_percentages.append(percentage)
    class_percentages.append(100)

    # remove duplicated values
    class_percentages = list(set(class_percentages))

    return sorted(class_percentages)


def get_tcg_ranks(values: list) -> list:
    """Return a list of TCG rank associated to input values
    input :[0,10,255,3598,3699,8555]
    output : [0,1,2,4,4,6]
    """
    # ①全てのマスのリスク値のトータル合計を求める
    sum_all_values = sum(values)

    # ②リスク値の小さい順番に、マスの順番を決める　※リスク値が同じ場合には、同じ順番を付ける
    # ③順番にリスク値を合計して、トータル合計で割って、そこまでのリスク割合を求める
    tcg_classes = []
    total_values = 0.0
    for value in values:
        total_values += value
        risk_rate = total_values / sum_all_values
        # ④ランクを付けて行く
        if risk_rate == 0:
            rank = 0
        elif risk_rate <= 0.1:
            rank = 1
        elif risk_rate <= 0.3:
            rank = 2
        elif risk_rate <= 0.5:
            rank = 3
        elif risk_rate <= 0.7:
            rank = 4
        elif risk_rate <= 0.9:
            rank = 5
        else:  # >0.9
            if tcg_classes[-1] == 5:
                rank = 6
            else:
                rank = 5
        tcg_classes.append(rank)
    return tcg_classes


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
    return color
