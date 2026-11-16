"""点数計算結果をUIで確認するための要約。"""

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Iterable, Mapping, Tuple


DISPLAY_NAMES = {
    "A31": "洪水",
    "A33": "土砂・傾斜",
    "A40": "津波",
    "HZD": "総合得点",
}


@dataclass(frozen=True)
class FieldScoreSummary:
    count: int
    minimum: int
    maximum: int
    average: float
    zero_count: int
    distribution: Tuple[Tuple[int, int], ...]


@dataclass(frozen=True)
class ScoreSummary:
    fields: Mapping[str, FieldScoreSummary]


def _integer_scores(name: str, values: Iterable[float]) -> Tuple[int, ...]:
    scores = []
    for value in values:
        number = float(value)
        if not isfinite(number) or number < 0:
            raise ValueError(f"{name}には0以上の整数を指定してください: {value}")
        integer = int(number)
        if number != integer:
            raise ValueError(f"{name}には0以上の整数を指定してください: {value}")
        scores.append(integer)
    return tuple(scores)


def summarize_scores(score_fields: Mapping[str, Iterable[float]]) -> ScoreSummary:
    """項目ごとの基本統計と点数別件数を返す。"""

    fields = {}
    expected_count = None
    for name, values in score_fields.items():
        scores = _integer_scores(name, values)
        if expected_count is None:
            expected_count = len(scores)
        elif len(scores) != expected_count:
            raise ValueError("点数項目のメッシュ数が一致していません")

        counts = Counter(scores)
        fields[name] = FieldScoreSummary(
            count=len(scores),
            minimum=min(scores, default=0),
            maximum=max(scores, default=0),
            average=mean(scores) if scores else 0.0,
            zero_count=counts[0],
            distribution=tuple(sorted(counts.items())),
        )
    return ScoreSummary(fields)


def format_score_summary(summary: ScoreSummary) -> str:
    """簡潔な日本語の点数分布表示へ整形する。"""

    lines = ["点数結果（最小 / 最大 / 平均 / 0件数）"]
    for name, field in summary.fields.items():
        display_name = DISPLAY_NAMES.get(name, name)
        lines.append(
            f"{display_name}: {field.minimum} / {field.maximum} / "
            f"{field.average:.1f} / {field.zero_count}件"
        )

    hzd = summary.fields.get("HZD")
    if hzd:
        lines.append("総合得点の点数別件数")
        entries = [f"{score}点:{count}件" for score, count in hzd.distribution]
        for start in range(0, len(entries), 8):
            lines.append(" / ".join(entries[start:start + 8]))
    return "\n".join(lines)
