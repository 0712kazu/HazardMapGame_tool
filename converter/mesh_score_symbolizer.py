from qgis.core import (
    QgsVectorLayer,
    QgsGraduatedSymbolRenderer,
    QgsClassificationRange,
    QgsFillSymbol,
    QgsRendererRange,
)


def graduate_layer(layer: QgsVectorLayer, target_field: str, breaks: list):
    # Set the symbol layer to the renderer
    # breaks list format = [[0, 1000, "Yellow"], [1001, 9999999999, "Blue"]]

    renderer = QgsGraduatedSymbolRenderer(target_field)

    for min, max, color in breaks:
        classificationRange = QgsClassificationRange(
            f"{min} < {target_field}<{max}", min, max
        )
        properties = {
            "color": color,
            "outline_color": "black",
            "outline_width": 0.1,
        }

        symbol = QgsFillSymbol.createSimple(properties)
        rendererRange = QgsRendererRange(classificationRange, symbol)
        renderer.addClassRange(rendererRange)

    layer.setRenderer(renderer)
    layer.triggerRepaint()


def get_mesh_value_from_percentage(mesh_values: list, percent_value: float) -> float:
    return len(mesh_values) * percent_value / 100


def get_color_from_range(break_id: int, nb_breaks: int) -> str:
    if nb_breaks == 1:
        color = "#fd8d3cff"
    elif nb_breaks == 2:
        color = {
            1: "#ffffb2ff",
            2: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 3:
        color = {
            1: "#ffffb2ff",
            2: "#fd8d3cff",
            3: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 4:
        color = {
            1: "#ffffb2ff",
            2: "#feb751ff",
            3: "#f45629f",
            4: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 5:
        color = {
            1: "#ffffb2ff",
            2: "#fecc5cff",
            3: "#fd8d3cff",
            4: "#f03b20ff",
            5: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 6:
        color = {
            1: "#ffffb2ff",
            2: "#fed66dff",
            3: "#fda649ff",
            4: "#f86c31ff",
            5: "#e62f21ff",
            6: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 7:
        color = {
            1: "#ffffb2ff",
            2: "#fedd79ff",
            3: "#feb751ff",
            4: "#fd8d3cff",
            5: "#f45629ff",
            6: "#df2722ff",
            7: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 8:
        color = {
            1: "#ffffb2ff",
            2: "#fee281ff",
            3: "#fec357ff",
            4: "#fd9f45ff",
            5: "#f97634ff",
            6: "#f24724ff",
            7: "#da2223ff",
            8: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 9:
        color = {
            1: "#ffffb2ff",
            2: "#ffe687ff",
            3: "#fecc5cff",
            4: "#fead4cff",
            5: "#fd8d3cff",
            6: "#f7642eff",
            7: "#f03b20ff",
            8: "#d71e23ff",
            9: "#bd0026ff",
        }.get(break_id, "#00000")
    elif nb_breaks == 10:
        color = {
            1: "#ffffb2ff",
            2: "#ffe88cff",
            3: "#fed266ff",
            4: "#feb751ff",
            5: "#fd9b43ff",
            6: "#fa7b36ff",
            7: "#f45629ff",
            8: "#ea3421ff",
            9: "#d41a23ff",
            10: "#bd0026ff",
        }.get(break_id, "#00000")
    return color
