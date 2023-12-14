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
        if max < constants.MAP_MIN_VALUE:
            max = constants.MAP_MIN_VALUE

        classificationRange = QgsClassificationRange(
            f"{min} < {target_field} < {max}", min, max
        )
        if color == "transparent":
            color_txt = "0,0,0,0"
        else:
            # convert #FFFFFF to "255,255,255,135"
            # with opacity as 135 value
            hex_color = color.lstrip("#")
            rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
            rgbtext = ", ".join(map(str, rgb))
            color_txt = rgbtext + ", 135"
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
    - class_percentages : [0,0,54,85,90,100] a list of percentages
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

    return class_percentages


def classify_values_tcg(values: list) -> list:
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

    # Convert to total percentages
    class_percentages = []
    total_sample = 0
    for i in range(0, 6):
        nb_elements_in_class = tcg_classes.count(i)
        total_sample += nb_elements_in_class
        percentage = total_sample / len(values) * 100
        class_percentages.append(percentage)
    class_percentages.append(100)

    return class_percentages


def get_color_from_range(break_id: int, nb_breaks: int) -> str:
    if nb_breaks == 1:
        color = "#fd8d3c"
    elif nb_breaks == 2:
        color = {
            1: "#ffffb2",
            2: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 3:
        color = {
            1: "#ffffb2",
            2: "#fd8d3c",
            3: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 4:
        color = {
            1: "#ffffb2",
            2: "#feb751",
            3: "#f45629",
            4: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 5:
        color = {
            1: "#ffffb2",
            2: "#fecc5c",
            3: "#fd8d3c",
            4: "#f03b20",
            5: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 6:
        color = {
            1: "#ffffb2",
            2: "#fed66d",
            3: "#fda649",
            4: "#f86c31",
            5: "#e62f21",
            6: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 7:
        color = {
            1: "#ffffb2",
            2: "#fedd79",
            3: "#feb751",
            4: "#fd8d3c",
            5: "#f45629",
            6: "#df2722",
            7: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 8:
        color = {
            1: "#ffffb2",
            2: "#fee281",
            3: "#fec357",
            4: "#fd9f45",
            5: "#f97634",
            6: "#f24724",
            7: "#da2223",
            8: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 9:
        color = {
            1: "#ffffb2",
            2: "#ffe687",
            3: "#fecc5c",
            4: "#fead4c",
            5: "#fd8d3c",
            6: "#f7642e",
            7: "#f03b20",
            8: "#d71e23",
            9: "#bd0026",
        }.get(break_id, "#00000")
    elif nb_breaks == 10:
        color = {
            1: "#ffffb2",
            2: "#ffe88c",
            3: "#fed266",
            4: "#feb751",
            5: "#fd9b43",
            6: "#fa7b36",
            7: "#f45629",
            8: "#ea3421",
            9: "#d41a23",
            10: "#bd0026",
        }.get(break_id, "#00000")
    return color
