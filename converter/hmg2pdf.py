from PyQt5.QtWidgets import QMessageBox
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsGraduatedSymbolRenderer,
    QgsClassificationRange,
    QgsFillSymbol,
    QgsRendererRange,
    QgsGradientColorRamp,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings,
    QgsClassificationJenks,
)
from qgis.PyQt.QtGui import QFont, QColor

import constants
from utils import add_xyz_basemap_layer


def label_pt_mesh(layer: QgsVectorLayer, expression: str, color: str) -> None:
    font_size = 26  # 26pt as specs

    # Create label settings
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = expression
    label_settings.isExpression = True

    # Set font properties
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial Rounded MT Bold", font_size))
    text_format.setSize(font_size)
    text_format.setColor(QColor(color))

    # set buffer
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1.5)  # mm
    buffer_settings.setColor(QColor("white"))
    text_format.setBuffer(buffer_settings)

    label_settings.setFormat(text_format)
    label_settings.placement = QgsPalLayerSettings.Placement.OverPoint
    label_settings.OverlapHandling = QgsPalLayerSettings.Property.OverlapHandling

    # Apply label settings to the layer
    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)

    layer.triggerRepaint()


def _display_only_layers(layers: list) -> None:
    """display only layers list (["layer_name1","layer_name2",...]),
    turn off other ones"""
    layer_tree = QgsProject.instance().layerTreeRoot()
    for layer in QgsProject.instance().mapLayers().values():
        if layer.name() in layers:
            layer_tree.findLayer(layer.id()).setItemVisibilityChecked(True)
        else:
            layer_tree.findLayer(layer.id()).setItemVisibilityChecked(False)


def _add_simple_fill_symbol_renderer(fill_color: str, stroke_color: str) -> QgsSymbol:
    properties = {
        "color": fill_color,
        "outline_color": stroke_color,
        "outline_width": 0.1,
    }

    symbol = QgsFillSymbol.createSimple(properties)
    return symbol


def _symbolize_fill_layer_simple(
    layer: QgsVectorLayer, fill_color: str, stroke_color: str
) -> None:
    symbol = _add_simple_fill_symbol_renderer(fill_color, stroke_color)
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def _symbolize_fill_layer_graduated(
    layer: QgsVectorLayer,
    cntField: str,
    nbClasses: int,
    start_color: str,
    end_color: str,
) -> None:
    properties = {
        "outline_style": "no",
        "outline_color": "000000",
        "outline_width": 0,
    }

    renderer = QgsGraduatedSymbolRenderer()
    renderer.setSourceSymbol(QgsFillSymbol.createSimple(properties))
    renderer.setClassAttribute(cntField)
    renderer.setClassificationMethod(QgsClassificationJenks())
    renderer.setSourceColorRamp(
        QgsGradientColorRamp(QColor(start_color), QColor(end_color))
    )
    renderer.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedColor)
    renderer.updateClasses(layer, nbClasses)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def set_hmg01_ans_refuge(gsi_std_lyr: QgsVectorLayer) -> None:
    # HMG01_ans : gsi standard only, refuges score and number, total hazard score, colors
    # TO DO , symbolize total score with label_id layer
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            "label_refuge",
            "label_id",
            "label_score",
            "seamless_refuge",
        ]
    )
    gsi_std_lyr.setOpacity(1)


def set_hmg02_base(gsi_std_lyr: QgsVectorLayer) -> None:
    # HNG02_base : gsi standard
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            "label_id",
        ]
    )

    gsi_std_lyr.setOpacity(1)


def set_hmg02_base_hillshade(
    gsi_std_lyr: QgsVectorLayer, gsi_hillshade_lyr: QgsVectorLayer
) -> None:
    # HMG02_base2: gsi standard and hillshade
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            "basemap_hillshade",
            "label_id",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)
    gsi_hillshade_lyr.setOpacity(0.5)


def set_hmg03_tile(gsi_std_lyr: QgsVectorLayer) -> None:
    # HMG03_tile: gsi_standard, turn off mesh id label
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
        ]
    )

    gsi_std_lyr.setOpacity(1)


def set_hmg04_use_landuse(gsi_std_lyr: QgsVectorLayer) -> None:
    # HMG04_use: Landuse symbol gsi_standard 50%, redisplay mesh_id
    # TODO: create seamless_landuse and symbolize
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            "seamless_landuse",
            "label_id",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg05_elev(gsi_std_lyr: QgsVectorLayer) -> None:
    # HMG05_elev: elevation, gsi_standard 50%, coloured elevation, hillshade
    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            "basemap_relief",
            "label_id",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg06_slope(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG06_g04: slope symbol & score, gsi_standard 50%
    target_field = constants.field_slope
    # label_score
    # TODO : check target field
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless slope opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(seamless_lyr, "angle", 10, "#ffffd4", "#993404")
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg07_earthquake(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG07_b01: quake symbol & score, gsi_standard 50%
    target_field = constants.field_earthquake
    # label_score
    # TODO : check target field
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless earthquake opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(
            seamless_lyr, "T30_I60_PS", 10, "#f1eef6", "#980043"
        )
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg08_tornado(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG08_a30: tornado symbol & score, gsi_standard 50%
    target_field = constants.field_tornado
    # label_score
    # TODO : check target field
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless tornado opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868")
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg09_flood(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG09_a31 : flood symbol & score, gsi_standard 50%
    target_field = constants.field_kozui
    # label_score
    # TODO : check target field

    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless flood opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(
            # To do : Create depth max field
            seamless_lyr,
            "A31_105",
            10,
            "#fcfbfd",
            "#3f007d",
        )
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg10_sediments(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG10_a33 : sediment symbol & score, gsi_standard 50%
    target_field = constants.field_sediments
    # label_score
    # TODO : check target field

    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless sediments opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868")
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg11_tsunami(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    #  HMG11_a40 : tsunami OR surge symbol & score, gsi_standard 50%
    # TO DO : check add tokyo surge data if tokyo to be added or not
    target_field = constants.field_tsunami

    # label_score
    # TODO : check target field

    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless tsunami or surge opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(
            seamless_lyr, f"h_{target_field}", 10, "#fcfbfd", "#3f007d"
        )
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg12_landslip(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG12_a46 : landslip symbol & score, gsi_standard 50%
    target_field = constants.field_jisuberi
    # label_score
    # TODO : check target field

    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless landslip opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868")
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)


def set_hmg13_disaster(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> None:
    # HMG13_a48 : disaster symbol & score, gsi_standard 50%
    target_field = constants.field_saigai
    # label_score
    # TODO : check target field

    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless disaster opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868")
        seamless_lyr.setOpacity(0.5)
    else:
        error_message = f"「seamless_{target_field}」レイヤが足りません。"
        QMessageBox.information(None, "エラー", error_message)

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
            "label_score",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)
