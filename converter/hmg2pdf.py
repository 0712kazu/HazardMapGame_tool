from qgis.core import (
    QgsVectorLayer,
    QgsGraduatedSymbolRenderer,
    QgsClassificationRange,
    QgsFillSymbol,
    QgsRendererRange,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings,
)
from qgis.PyQt.QtGui import QFont, QColor


def label_pt_mesh(layer: QgsVectorLayer, expression: str, color: str):
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
