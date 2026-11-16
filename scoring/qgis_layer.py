"""QGISベクタレイヤーとゲーム得点計算の接続。"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import QMetaType
from qgis.core import NULL, QgsField, QgsVectorLayer

from .game_scores import GameScores, calculate_game_scores
from .score_summary import ScoreSummary, summarize_scores


INPUT_FIELDS = {
    "flood": "t_flood",
    "sediment": "t_sediment",
    "slope": "t_slope",
    "tsunami": "t_tsunami",
}

OUTPUT_FIELDS = {
    "a31": "A31",
    "a33": "A33",
    "a40": "A40",
    "base_hzd": "base_hzd",
    "hzd": "HZD",
    "multiplier": "hzd_multiplier",
}


class LayerScoringError(RuntimeError):
    """レイヤーの検証または更新に失敗した場合のエラー。"""


@dataclass(frozen=True)
class LayerScoringResult:
    feature_count: int
    hzd_multiplier: float
    maximum_a33: int
    maximum_base_hzd: int
    maximum_hzd: int
    sediment_slope_overlap_count: int
    score_summary: ScoreSummary


def _integer_field_type():
    """QGIS 3 (Qt 5) とQGIS 4 (Qt 6) の両方で使える整数型。"""

    try:
        return QMetaType.Type.Int
    except AttributeError:
        from qgis.PyQt.QtCore import QVariant

        return QVariant.Int


def _double_field_type():
    """QGIS 3 (Qt 5) とQGIS 4 (Qt 6) の両方で使える実数型。"""

    try:
        return QMetaType.Type.Double
    except AttributeError:
        from qgis.PyQt.QtCore import QVariant

        return QVariant.Double


def _number_or_zero(value, field_name: str, feature_id: int) -> float:
    if value is None or value == NULL:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise LayerScoringError(
            f"{field_name}に数値以外の値があります（feature id: {feature_id}）"
        ) from error


def _add_output_fields(layer: QgsVectorLayer) -> None:
    existing = set(layer.fields().names())
    fields = []
    for key in ("a31", "a33", "a40", "base_hzd", "hzd"):
        name = OUTPUT_FIELDS[key]
        if name not in existing:
            fields.append(QgsField(name, _integer_field_type()))
    multiplier_name = OUTPUT_FIELDS["multiplier"]
    if multiplier_name not in existing:
        fields.append(QgsField(multiplier_name, _double_field_type()))

    for field in fields:
        if not layer.addAttribute(field):
            raise LayerScoringError(
                f"点数出力フィールドを追加できませんでした: {field.name()}"
            )
    layer.updateFields()


def _attribute_indexes(layer: QgsVectorLayer) -> Dict[str, int]:
    indexes = {
        key: layer.fields().indexFromName(name)
        for key, name in OUTPUT_FIELDS.items()
    }
    missing = [OUTPUT_FIELDS[key] for key, index in indexes.items() if index < 0]
    if missing:
        raise LayerScoringError(
            "点数出力フィールドを確認できません: " + ", ".join(missing)
        )
    return indexes


def _write_scores(
    layer: QgsVectorLayer,
    feature_ids: List[int],
    scores: GameScores,
) -> None:
    indexes = _attribute_indexes(layer)
    values = {
        "a31": scores.a31,
        "a33": scores.a33,
        "a40": scores.a40,
        "base_hzd": scores.base_hzd,
        "hzd": scores.hzd,
    }

    for position, feature_id in enumerate(feature_ids):
        for key, score_values in values.items():
            if not layer.changeAttributeValue(
                feature_id, indexes[key], score_values[position]
            ):
                raise LayerScoringError(
                    f"{OUTPUT_FIELDS[key]}を更新できませんでした（feature id: {feature_id}）"
                )
        if not layer.changeAttributeValue(
            feature_id, indexes["multiplier"], scores.hzd_multiplier
        ):
            raise LayerScoringError(
                "hzd_multiplierを更新できませんでした"
                f"（feature id: {feature_id}）"
            )


def calculate_layer_scores(
    layer: QgsVectorLayer,
    *,
    hzd_multiplier: Optional[float] = None,
    hzd_target_maximum: int = 15,
    a33_maximum: int = 6,
) -> LayerScoringResult:
    """レイヤーの`t_*`からゲーム得点を計算して同じレイヤーへ保存する。

    `hzd_multiplier`を指定した再計算では、その倍率を維持する。`None`の場合だけ
    現在の点数分布と目標点から初期倍率を計算する。
    """

    if layer is None or not layer.isValid():
        raise LayerScoringError("有効なメッシュレイヤーを選択してください")
    if layer.isEditable():
        raise LayerScoringError(
            "対象レイヤーは編集中です。編集内容を保存してから再実行してください"
        )

    field_names = set(layer.fields().names())
    missing = [name for name in INPUT_FIELDS.values() if name not in field_names]
    if missing:
        raise LayerScoringError(
            "点数計算に必要なフィールドがありません: " + ", ".join(missing)
        )

    features = list(layer.getFeatures())
    if not features:
        raise LayerScoringError("対象レイヤーにメッシュがありません")

    feature_ids = [feature.id() for feature in features]
    inputs = {
        key: [
            _number_or_zero(feature[field_name], field_name, feature.id())
            for feature in features
        ]
        for key, field_name in INPUT_FIELDS.items()
    }
    overlap_count = sum(
        sediment > 0 and slope > 0
        for sediment, slope in zip(inputs["sediment"], inputs["slope"])
    )
    scores = calculate_game_scores(
        inputs["flood"],
        inputs["sediment"],
        inputs["slope"],
        inputs["tsunami"],
        hzd_multiplier=hzd_multiplier,
        hzd_target_maximum=hzd_target_maximum,
        a33_maximum=a33_maximum,
    )

    if not layer.startEditing():
        raise LayerScoringError("対象レイヤーの編集を開始できませんでした")
    try:
        _add_output_fields(layer)
        _write_scores(layer, feature_ids, scores)
        if not layer.commitChanges():
            errors = "; ".join(layer.commitErrors())
            raise LayerScoringError(
                "点数を保存できませんでした" + (f": {errors}" if errors else "")
            )
    except Exception:
        if layer.isEditable():
            layer.rollBack()
        raise

    return LayerScoringResult(
        feature_count=len(features),
        hzd_multiplier=scores.hzd_multiplier,
        maximum_a33=max(scores.a33, default=0),
        maximum_base_hzd=max(scores.base_hzd, default=0),
        maximum_hzd=max(scores.hzd, default=0),
        sediment_slope_overlap_count=overlap_count,
        score_summary=summarize_scores(
            {
                "A31": scores.a31,
                "A33": scores.a33,
                "A40": scores.a40,
                "HZD": scores.hzd,
            }
        ),
    )
