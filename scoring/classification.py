"""災害リスク値をゲーム用ランクへ変換する純粋計算。"""

from collections import Counter
from math import isfinite
from statistics import mean, pstdev
from typing import Iterable, List, Sequence, Tuple


def _values(values: Iterable[float]) -> Tuple[float, ...]:
    result = tuple(float(value) for value in values)
    for value in result:
        if not isfinite(value) or value < 0:
            raise ValueError("リスク値には0以上の有限数を指定してください")
    return result


def _validate_max_rank(max_rank: int) -> None:
    if max_rank < 1:
        raise ValueError("最大ランクは1以上にしてください")


def classify_tcg_ranks(
    values: Iterable[float], max_rank: int = 6
) -> List[int]:
    """累積リスク割合をTCG方式でランクへ変換する。

    6ランク時の境界は従来どおり10%、30%、50%、70%、90%となる。
    同値には同じランクを割り当て、0は常に0とする。極端に少数のデータだけで
    最大ランクにならないよう、直前の正値が最大ランクの1つ下へ達していない場合は
    最上位を1段抑える。
    """

    scores = _values(values)
    _validate_max_rank(max_rank)
    if not scores:
        return []
    if max_rank == 1:
        return [0 if value == 0 else 1 for value in scores]

    total = sum(scores)
    if total == 0:
        return [0 for _ in scores]

    value_counts = Counter(scores)
    ranks_by_value = {0.0: 0}
    cumulative = 0.0
    previous_positive_rank = 0
    for value in sorted(value_counts):
        if value == 0:
            continue
        cumulative += value * value_counts[value]
        risk_rate = cumulative / total

        rank = max_rank
        for candidate in range(1, max_rank):
            boundary = (candidate - 0.5) / (max_rank - 1)
            if risk_rate <= boundary:
                rank = candidate
                break

        if rank == max_rank and previous_positive_rank < max_rank - 1:
            rank = max_rank - 1
        ranks_by_value[value] = rank
        previous_positive_rank = rank

    return [ranks_by_value[value] for value in scores]


def classify_standard_deviation_ranks(
    values: Iterable[float], max_rank: int = 6
) -> List[int]:
    """正のリスク値だけを母集団として標準偏差ランクを計算する。

    0は欠測扱いにせず、明示的な0点として統計計算から除外する。正値がすべて
    同じ場合は差がないため全て1点とする。
    """

    scores = _values(values)
    _validate_max_rank(max_rank)
    positives = [value for value in scores if value > 0]
    if not positives:
        return [0 for _ in scores]
    if max_rank == 1 or len(set(positives)) == 1:
        return [0 if value == 0 else 1 for value in scores]

    average = mean(positives)
    deviation = pstdev(positives)
    if deviation == 0:
        return [0 if value == 0 else 1 for value in scores]

    lower = average - deviation
    width = (2 * deviation) / (max_rank - 1)
    boundaries = [lower + width * rank for rank in range(1, max_rank)]

    ranks = []
    for value in scores:
        if value == 0:
            ranks.append(0)
            continue
        rank = 1
        for boundary in boundaries:
            if value <= boundary:
                break
            rank += 1
        ranks.append(min(rank, max_rank))
    return ranks


def ranks_to_percentages(
    ranks: Sequence[int], max_rank: int
) -> List[float]:
    """ランク境界を既存プレビューUI用の累積メッシュ割合へ変換する。"""

    _validate_max_rank(max_rank)
    if not ranks:
        return [0.0] * max_rank + [100.0]
    return [
        sum(rank <= boundary for rank in ranks) / len(ranks) * 100
        for boundary in range(0, max_rank + 1)
    ]
