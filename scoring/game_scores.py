"""「守れ！サイガイ防衛隊」向け得点計算。

このモジュールはQGIS APIに依存させない。点数調整をQGISの画面からも
自動テストからも同じ規則で実行できるようにするためである。
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from math import isfinite
from typing import Iterable, Mapping, Optional, Sequence, Tuple


Number = float


@dataclass(frozen=True)
class GameScores:
    """メッシュ順を維持したゲーム用得点一式。"""

    a31: Tuple[int, ...]
    a33: Tuple[int, ...]
    a40: Tuple[int, ...]
    base_hzd: Tuple[int, ...]
    hzd: Tuple[int, ...]
    hzd_multiplier: float


@dataclass(frozen=True)
class HzdScores:
    """災害項目を限定しない総合得点計算結果。"""

    base_hzd: Tuple[int, ...]
    hzd: Tuple[int, ...]
    multiplier: float


def _validated_scores(name: str, values: Iterable[Number]) -> Tuple[float, ...]:
    scores = tuple(float(value) for value in values)
    for value in scores:
        if not isfinite(value):
            raise ValueError(f"{name}には有限の数値を指定してください: {value}")
        if value < 0:
            raise ValueError(f"{name}に負の点数は指定できません: {value}")
    return scores


def _ceil(value: float) -> int:
    """浮動小数点誤差で整数が1点増えないようDecimalで切り上げる。"""

    return int(Decimal(str(value)).to_integral_value(rounding=ROUND_CEILING))


def _scale_a33(
    sediment_scores: Sequence[float],
    slope_scores: Sequence[float],
    maximum: int,
) -> Tuple[int, ...]:
    raw_scores = tuple(
        sediment + slope
        for sediment, slope in zip(sediment_scores, slope_scores)
    )
    raw_maximum = max(raw_scores, default=0.0)

    if raw_maximum == 0:
        return tuple(0 for _ in raw_scores)
    if raw_maximum <= maximum:
        return tuple(_ceil(score) if score > 0 else 0 for score in raw_scores)

    factor = Decimal(maximum) / Decimal(str(raw_maximum))
    return tuple(
        0
        if score == 0
        else int(
            (Decimal(str(score)) * factor).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        for score in raw_scores
    )


def suggest_hzd_multiplier(
    base_scores: Iterable[Number], target_maximum: int = 15
) -> float:
    """総合得点を引き上げるための初期倍率を返す。

    最大値が目標以上なら縮小せず1倍とする。目標は初期値の提案にだけ使い、
    最終HZDには上限を設けない。
    """

    scores = _validated_scores("base_hzd", base_scores)
    if target_maximum <= 0:
        raise ValueError("target_maximumは1以上にしてください")

    current_maximum = max(scores, default=0.0)
    if current_maximum == 0 or current_maximum >= target_maximum:
        return 1.0
    return float(Decimal(target_maximum) / Decimal(str(current_maximum)))


def calculate_hzd(
    components: Mapping[str, Sequence[Number]],
    *,
    multiplier: Optional[float] = None,
    target_maximum: int = 15,
) -> HzdScores:
    """任意の災害別点数を合計し、総合得点だけを一律補正する。

    現在のゲーム出力はA31・A33・A40だけを渡す。将来、地震などを採用する
    場合はコンポーネントを追加でき、既存3項目の計算規則は変更しなくてよい。
    """

    validated = {
        name: _validated_scores(name, values)
        for name, values in components.items()
    }
    if not validated:
        return HzdScores((), (), 1.0 if multiplier is None else float(multiplier))

    lengths = {len(values) for values in validated.values()}
    if len(lengths) != 1:
        raise ValueError("総合得点の災害別メッシュ数が一致していません")

    base_hzd = tuple(
        sum(
            _ceil(values[index]) if values[index] > 0 else 0
            for values in validated.values()
        )
        for index in range(next(iter(lengths)))
    )
    selected_multiplier = (
        suggest_hzd_multiplier(base_hzd, target_maximum)
        if multiplier is None
        else float(multiplier)
    )
    if not isfinite(selected_multiplier) or selected_multiplier <= 0:
        raise ValueError("hzd_multiplierは0より大きい有限の数値にしてください")

    decimal_multiplier = Decimal(str(selected_multiplier))
    hzd = tuple(
        0
        if score == 0
        else int(
            (Decimal(score) * decimal_multiplier).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        for score in base_hzd
    )
    return HzdScores(base_hzd, hzd, selected_multiplier)


def calculate_game_scores(
    flood_scores: Iterable[Number],
    sediment_scores: Iterable[Number],
    slope_scores: Iterable[Number],
    tsunami_scores: Iterable[Number],
    *,
    hzd_multiplier: Optional[float] = None,
    hzd_target_maximum: int = 15,
    a33_maximum: int = 6,
) -> GameScores:
    """A31・A33・A40とゲーム補正済みHZDを計算する。

    A33は土砂と傾斜の合計を全メッシュ共通の倍率で最大6点へ収める。
    HZDは災害別得点を変えず、合計にだけ一律倍率を掛けて切り上げる。
    HZDに上限は設けない。
    """

    flood = _validated_scores("t_flood", flood_scores)
    sediment = _validated_scores("t_sediment", sediment_scores)
    slope = _validated_scores("t_slope", slope_scores)
    tsunami = _validated_scores("t_tsunami", tsunami_scores)

    lengths = {len(flood), len(sediment), len(slope), len(tsunami)}
    if len(lengths) != 1:
        raise ValueError("災害別点数のメッシュ数が一致していません")
    if a33_maximum <= 0:
        raise ValueError("a33_maximumは1以上にしてください")

    a31 = tuple(_ceil(score) if score > 0 else 0 for score in flood)
    a33 = _scale_a33(sediment, slope, a33_maximum)
    a40 = tuple(_ceil(score) if score > 0 else 0 for score in tsunami)
    totals = calculate_hzd(
        {"A31": a31, "A33": a33, "A40": a40},
        multiplier=hzd_multiplier,
        target_maximum=hzd_target_maximum,
    )
    return GameScores(
        a31,
        a33,
        a40,
        totals.base_hzd,
        totals.hzd,
        totals.multiplier,
    )
