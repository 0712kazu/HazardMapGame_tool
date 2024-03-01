import os

from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsGraduatedSymbolRenderer,
    QgsGradientColorRamp,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsFillSymbol,
    QgsMarkerSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings,
    QgsClassificationJenks,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsField,
    QgsFeatureRequest,
)
from qgis.PyQt.QtGui import QFont, QColor, QPainter

import constants


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


def _add_simple_fill_symbol_renderer(
    fill_color: str, stroke_color: str, stroke_width: float
) -> QgsSymbol:
    properties = {
        "color": fill_color,
        "outline_color": stroke_color,
        "outline_width": stroke_width,
    }

    if stroke_width == 0:
        properties["outline_style"] = "no"

    symbol = QgsFillSymbol.createSimple(properties)
    return symbol


def _add_point_symbol_renderer(
    shape: str, color: str, stroke_color: str, stroke_width: float, size_mm: float
) -> QgsSymbol:
    properties = {
        "name": shape,
        "color": color,
        "outline_color": stroke_color,
        "outline_width": stroke_width,
        "size": size_mm,
        "size_unit": "MM",
    }

    if stroke_width == 0:
        properties["outline_style"] = "no"

    symbol = QgsMarkerSymbol.createSimple(properties)

    return symbol


def _symbolize_fill_layer_simple(
    layer: QgsVectorLayer, fill_color: str, stroke_color: str, stroke_width: float
) -> None:
    symbol = _add_simple_fill_symbol_renderer(fill_color, stroke_color, stroke_width)
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


def _symbolize_fill_layer_categorized(
    layer: QgsVectorLayer, category_field: str, category_mapping: list
) -> None:
    categories = []

    for cat in category_mapping:
        stroke_width = 0
        symbol = _add_simple_fill_symbol_renderer(
            cat["fill_color"], cat["stroke_color"], stroke_width
        )
        category = QgsRendererCategory(
            cat["value"],
            symbol,
            cat["value"],
        )
        categories.append(category)
    renderer = QgsCategorizedSymbolRenderer(category_field, categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def _symbolize_point_layer_categorized(
    layer: QgsVectorLayer, category_field: str, category_mapping: list
) -> None:
    categories = []

    for cat in category_mapping:
        symbol = _add_point_symbol_renderer(
            cat["shape"],
            cat["color"],
            cat["stroke_color"],
            cat["stroke_width"],
            cat["size_mm"],
        )
        category = QgsRendererCategory(
            cat["value"],
            symbol,
            cat["value"],
        )
        categories.append(category)
    renderer = QgsCategorizedSymbolRenderer(category_field, categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def set_hmg01_ans_refuge(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG01_ans : gsi standard only, refuges score & count, total hazard score, colors
    # return result as list of missing layers text

    miss_lyr = []
    # symbolize total score with label_id layer
    label_pt_mesh(label_mesh_score, f'"{constants.field_hazard_score}"', "red")

    if QgsProject.instance().mapLayersByName("hazard_score"):
        hazard_score_lyr = QgsProject.instance().mapLayersByName("hazard_score")[0]
        category_mapping = [
            {
                "value": "1",
                "shape": "circle",
                "size_mm": 40,
                "color": "#fdf7c0",
                "stroke_color": "#000000",
                "stroke_width": 0,
            },
            {
                "value": "2",
                "shape": "circle",
                "size_mm": 40,
                "color": "#ffdf9b",
                "stroke_color": "#000000",
                "stroke_width": 0,
            },
            {
                "value": "3",
                "shape": "circle",
                "size_mm": 40,
                "color": "#fab6b2",
                "stroke_color": "#000000",
                "stroke_width": 0,
            },
        ]

        _symbolize_point_layer_categorized(
            hazard_score_lyr, constants.field_hazard_rank, category_mapping
        )
        hazard_score_lyr.setOpacity(1)
        hazard_score_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        # return missing layer to add in list
        miss_lyr.append["hazard_score"]

    # symbolize POINT refuge
    target_field = constants.field_refuge
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]

        svg_path = os.path.join(
            os.path.dirname(__file__),
            constants.data_dir,
            "styles",
            "refuge_marker.svg",
        )
        symbol = QgsSymbol.defaultSymbol(seamless_lyr.geometryType())
        symbol_layer = QgsSvgMarkerSymbolLayer(svg_path)
        symbol_layer.setSize(5)  # in mm
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        seamless_lyr.setRenderer(renderer)
        seamless_lyr.triggerRepaint()
        seamless_lyr.setOpacity(1)

    else:
        miss_lyr.append(f"seamless_{target_field}")

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"label_{target_field}",
            "label_id",
            "label_score",
            f"seamless_{target_field}",
            "hazard_score",
        ]
    )
    gsi_std_lyr.setOpacity(1)

    return miss_lyr


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


def set_hmg04_landuse(gsi_std_lyr: QgsVectorLayer) -> list:
    # HMG04_use: Landuse symbol gsi_standard 50%, redisplay mesh_id
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_landuse

    # symbolize seamless_landuse by category and symbolize as 0.7 opacity
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]

        category_mapping = [
            {"value": "0100", "fill_color": "#ffee7f", "stroke_color": "#000000"},
            {"value": "0200", "fill_color": "#fbf8da", "stroke_color": "#000000"},
            {"value": "0500", "fill_color": "#86e192", "stroke_color": "#000000"},
            {"value": "0600", "fill_color": "#fec37f", "stroke_color": "#000000"},
            {"value": "0700", "fill_color": "#ff7f7f", "stroke_color": "#000000"},
            {"value": "0901", "fill_color": "#c4c4c4", "stroke_color": "#000000"},
            {"value": "0902", "fill_color": "#e3e3e3", "stroke_color": "#000000"},
            {"value": "1000", "fill_color": "#d2b98d", "stroke_color": "#000000"},
            {"value": "1100", "fill_color": "#7b8aff", "stroke_color": "#000000"},
            {"value": "1400", "fill_color": "#fcf8e2", "stroke_color": "#000000"},
            {"value": "1500", "fill_color": "#8feaff", "stroke_color": "#000000"},
            {"value": "1600", "fill_color": "#9bfd9b", "stroke_color": "#000000"},
            {"value": "0000", "fill_color": "#e8e8e8", "stroke_color": "#000000"},
        ]

        _symbolize_fill_layer_categorized(seamless_lyr, "土地利用種", category_mapping)
        seamless_lyr.setOpacity(0.7)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

    _display_only_layers(
        [
            "waku",
            "mesh_score",
            "basemap_standard",
            f"seamless_{target_field}",
            "label_id",
        ]
    )

    gsi_std_lyr.setOpacity(0.5)

    return miss_lyr


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
) -> list:
    # HMG06_g04: slope symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_slope
    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless slope opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(seamless_lyr, "angle", 10, "#ffffd4", "#993404")
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg07_earthquake(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG07_b01: quake symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_earthquake
    # label_score
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
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg08_tornado(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG08_a30: tornado symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_tornado
    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless tornado opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868", 0.1)
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg09_flood(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG09_a31 : flood symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_kozui

    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless flood opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(
            seamless_lyr,
            "depth",
            10,
            "#aa95c8",
            "#3f007d",
        )
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg10_sediments(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG10_a33 : sediment symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_sediments

    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless sediments opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868", 0.1)
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg11_tsunami(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer, target_field: str
) -> list:
    #  HMG11_a40 : tsunami OR surge symbol (target_field) & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless tsunami or surge opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_graduated(
            seamless_lyr, f"h_{target_field}", 10, "#e0e0ee", "#3f007d"
        )
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg12_landslip(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG12_a46 : landslip symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_jisuberi
    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless landslip opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868", 0.1)
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def set_hmg13_disaster(
    gsi_std_lyr: QgsVectorLayer, label_mesh_score: QgsVectorLayer
) -> list:
    # HMG13_a48 : disaster symbol & score, gsi_standard 50%
    # return result as list of missing layers)
    miss_lyr = []

    target_field = constants.field_saigai
    # label_score
    label_pt_mesh(label_mesh_score, f'"t_{target_field}"', "red")

    # symbolyze seamless disaster opacity 0.5
    if QgsProject.instance().mapLayersByName(f"seamless_{target_field}"):
        seamless_lyr = QgsProject.instance().mapLayersByName(
            f"seamless_{target_field}"
        )[0]
        _symbolize_fill_layer_simple(seamless_lyr, "#FF0000", "#686868", 0.1)
        seamless_lyr.setOpacity(0.5)
        seamless_lyr.setBlendMode(QPainter.CompositionMode_Multiply)
    else:
        miss_lyr.append(f"seamless_{target_field}")

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
    return miss_lyr


def calculate_hazard_rank(scored_hazard_lyr: QgsVectorLayer) -> QgsVectorLayer:
    hazard_score_field = constants.field_hazard_score
    rank_score_field = constants.field_hazard_rank

    field_values = [
        feature[hazard_score_field] for feature in scored_hazard_lyr.getFeatures()
    ]
    values = sorted(field_values)

    # calculate rank list
    hzd_ranks = _get_hzd_ranks(values)

    # add hzd rank field if not exists
    if rank_score_field not in scored_hazard_lyr.fields().names():
        scored_hazard_lyr.startEditing()
        scored_hazard_lyr.addAttribute(QgsField(rank_score_field, QVariant.Int))
        scored_hazard_lyr.commitChanges()

    # calculate hzd rank
    scored_hazard_lyr.startEditing()
    # input y_values to be in ascending order :[0,10,255,3598,3699,8555]
    # associated hzd_ranks : [0,1,2,4,4,6]
    # Sort the features based on hazard score ascending order
    request = QgsFeatureRequest().addOrderBy(hazard_score_field, ascending=True)
    features = scored_hazard_lyr.getFeatures(request)

    # Update the hzd rank field based on the sorting order
    for index, feature in enumerate(features):
        feature.setAttribute(rank_score_field, hzd_ranks[index])
        scored_hazard_lyr.updateFeature(feature)

    # Stop editing and save changes
    scored_hazard_lyr.commitChanges()
    return scored_hazard_lyr


def _get_hzd_ranks(values: list) -> list:
    """Return a list of Hazard rank associated to input values
    input :[0,1,2,2,8,14]
    output : [1,1,1,1,2,3]
    全ての枠の合計点数を総合計を求める。
    合計点数が小さい順に並べて、累計を求める。
    累計が総合計の50%未満:黄色 (rank 1)
    累計が総合計の50%以上80%未満:オレンジ (rank 2)
    累計が総合計の80%以上:赤 (rank 3)
    """
    # ①全てのマスのリスク値のトータル合計を求める
    sum_all_values = sum(values)

    hzd_classes = []
    hzd_values_dict = {}  # use dict to have unique rank for same value

    total_values = 0.0
    for value in values:
        total_values += value
        if sum_all_values == 0:
            risk_rate = 0
        else:
            risk_rate = total_values / sum_all_values
        # ランクを付けて行く
        if risk_rate < 0.5:
            rank = 1
        elif risk_rate < 0.8:
            rank = 2
        else:  # >=0.8
            rank = 3
        hzd_classes.append(rank)
        hzd_values_dict[value] = rank  # will have the upper rank for same value

    # make revised hzd values with same rank for same values
    hzd_ranks = []
    for value in values:
        hzd_ranks.append(hzd_values_dict[value])

    return hzd_ranks
