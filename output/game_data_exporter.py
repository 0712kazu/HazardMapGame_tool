"""処理用GeoPackageとサイガイ防衛隊用GeoJSONの分離出力。"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    NULL,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)


GAME_FIELDS = ("ID", "land_rate", "A31", "A33", "A40", "HZD")
SOURCE_FIELDS = ("id", "land_rate", "A31", "A33", "A40", "HZD")


class OutputValidationError(RuntimeError):
    """出力前後のデータ検証に失敗した場合のエラー。"""


@dataclass(frozen=True)
class ExportResult:
    processing_gpkg_path: str
    game_geojson_path: str
    feature_count: int


def safe_file_prefix(value: str) -> str:
    """WindowsとmacOSの両方で使用できるファイル名へ整形する。"""

    prefix = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    prefix = prefix.rstrip(". ")
    return prefix or datetime.now().strftime("%Y%m%d%H%M%S")


def _is_null(value) -> bool:
    return value is None or value == NULL


def _integer(value, field_name: str, feature_id: int) -> int:
    if _is_null(value):
        return 0
    try:
        number = float(value)
        integer = int(number)
    except (TypeError, ValueError) as error:
        raise OutputValidationError(
            f"{field_name}に整数以外の値があります（feature id: {feature_id}）"
        ) from error
    if number != integer or integer < 0:
        raise OutputValidationError(
            f"{field_name}に0以上の整数以外の値があります"
            f"（feature id: {feature_id}, value: {value}）"
        )
    return integer


def _land_rate(value, feature_id: int) -> float:
    if _is_null(value):
        raise OutputValidationError(
            f"land_rateがありません（feature id: {feature_id}）"
        )
    try:
        rate = float(value)
    except (TypeError, ValueError) as error:
        raise OutputValidationError(
            f"land_rateが数値ではありません（feature id: {feature_id}）"
        ) from error
    if not 0 <= rate <= 1:
        raise OutputValidationError(
            f"land_rateは0〜1で指定してください（feature id: {feature_id}）"
        )
    return rate


def _validate_source(layer: QgsVectorLayer) -> None:
    if layer is None or not layer.isValid():
        raise OutputValidationError("有効なmesh_scoreレイヤーを選択してください")
    if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise OutputValidationError("mesh_scoreはポリゴンレイヤーである必要があります")
    missing = [name for name in SOURCE_FIELDS if name not in layer.fields().names()]
    if missing:
        raise OutputValidationError(
            "出力に必要なフィールドがありません: " + ", ".join(missing)
        )
    if layer.featureCount() == 0:
        raise OutputValidationError("出力対象のメッシュがありません")


def _make_game_layer(source: QgsVectorLayer) -> QgsVectorLayer:
    game_layer = QgsVectorLayer(
        "MultiPolygon?crs=EPSG:4326",
        "saigaiboueitai",
        "memory",
    )
    provider = game_layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("ID", QMetaType.Type.Int),
            QgsField("land_rate", QMetaType.Type.Double),
            QgsField("A31", QMetaType.Type.Int),
            QgsField("A33", QMetaType.Type.Int),
            QgsField("A40", QMetaType.Type.Int),
            QgsField("HZD", QMetaType.Type.Int),
        ]
    )
    game_layer.updateFields()

    destination_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(
        source.crs(),
        destination_crs,
        QgsProject.instance().transformContext(),
    )
    output_features = []
    seen_ids = set()
    for source_feature in source.getFeatures():
        feature_id = source_feature.id()
        mesh_id = _integer(source_feature["id"], "id", feature_id)
        if mesh_id in seen_ids:
            raise OutputValidationError(f"メッシュIDが重複しています: {mesh_id}")
        seen_ids.add(mesh_id)

        geometry = source_feature.geometry()
        if geometry.isNull() or geometry.isEmpty():
            raise OutputValidationError(
                f"形状が空のメッシュがあります（ID: {mesh_id}）"
            )
        if not geometry.isGeosValid():
            geometry = geometry.makeValid()
        if QgsWkbTypes.geometryType(geometry.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise OutputValidationError(
                f"ポリゴンへ修復できない形状があります（ID: {mesh_id}）"
            )
        geometry.transform(transform)
        if not QgsWkbTypes.isMultiType(geometry.wkbType()):
            if not geometry.convertToMultiType():
                raise OutputValidationError(
                    f"MultiPolygonへ変換できない形状があります（ID: {mesh_id}）"
                )

        output_feature = QgsFeature(game_layer.fields())
        output_feature.setGeometry(geometry)
        output_feature.setAttributes(
            [
                mesh_id,
                _land_rate(source_feature["land_rate"], feature_id),
                _integer(source_feature["A31"], "A31", feature_id),
                _integer(source_feature["A33"], "A33", feature_id),
                _integer(source_feature["A40"], "A40", feature_id),
                _integer(source_feature["HZD"], "HZD", feature_id),
            ]
        )
        output_features.append(output_feature)

    success, _ = provider.addFeatures(output_features)
    if not success:
        raise OutputValidationError("ゲーム用メッシュを作成できませんでした")
    game_layer.updateExtents()
    return game_layer


def _write_layer(
    layer: QgsVectorLayer,
    path: str,
    driver_name: str,
    layer_name: Optional[str] = None,
) -> None:
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = driver_name
    options.fileEncoding = "UTF-8"
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    if layer_name:
        options.layerName = layer_name
    if driver_name == "GeoJSON":
        options.layerOptions = ["RFC7946=YES", "COORDINATE_PRECISION=7"]

    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        path,
        QgsProject.instance().transformContext(),
        options,
    )
    error = result[0]
    error_message = result[1]
    if error != QgsVectorFileWriter.NoError:
        raise OutputValidationError(
            f"{os.path.basename(path)}を書き出せませんでした: {error_message}"
        )


def _validate_game_output(path: str, expected_count: int) -> None:
    layer = QgsVectorLayer(path, "game_output_validation", "ogr")
    if not layer.isValid():
        raise OutputValidationError("書き出したゲーム用GeoJSONを読み込めません")
    if layer.crs().authid() != "EPSG:4326":
        raise OutputValidationError("ゲーム用GeoJSONがEPSG:4326ではありません")
    if not QgsWkbTypes.isMultiType(layer.wkbType()):
        raise OutputValidationError("ゲーム用GeoJSONがMultiPolygonではありません")
    if tuple(layer.fields().names()) != GAME_FIELDS:
        raise OutputValidationError(
            "ゲーム用GeoJSONの属性が仕様と一致しません: "
            + ", ".join(layer.fields().names())
        )
    if layer.featureCount() != expected_count:
        raise OutputValidationError("ゲーム用GeoJSONのメッシュ数が一致しません")


def export_game_data(
    source: QgsVectorLayer,
    output_directory: str,
    file_prefix: str,
) -> ExportResult:
    """処理用GPKGと最小構成のゲーム用GeoJSONを別々に出力する。"""

    _validate_source(source)
    if not output_directory:
        raise OutputValidationError("出力先フォルダーを指定してください")
    os.makedirs(output_directory, exist_ok=True)
    prefix = safe_file_prefix(file_prefix)
    processing_path = os.path.join(output_directory, f"{prefix}_hmg_analysis.gpkg")
    game_path = os.path.join(output_directory, f"{prefix}_saigaiboueitai.geojson")

    game_layer = _make_game_layer(source)
    _write_layer(source, processing_path, "GPKG", "mesh_score")
    _write_layer(game_layer, game_path, "GeoJSON")
    _validate_game_output(game_path, source.featureCount())
    return ExportResult(processing_path, game_path, source.featureCount())
