"""浸水区分の変換表と、入力値の検証。

未対応の区分を無災害（0）として扱わないため、QGIS に依存しない形で
変換前の値を検証する。
"""

from collections import Counter
from numbers import Number


FLOOD_V1_FIELDS = ("A31_001",)
FLOOD_V2_FIELDS = (
    "A31_101",
    "A31_105",
    "A31_201",
    "A31_205",
    "A31_301",
    "A31_305",
    "A31_401",
    "A31_405",
    "A31a_101",
    "A31a_105",
    "A31a_201",
    "A31a_205",
    "A31a_301",
    "A31a_305",
    "A31a_401",
    "A31a_405",
)

FLOOD_V1_DEPTHS = {
    11: 0.2,
    12: 0.7,
    13: 1.4,
    14: 3,
    15: 7,
    21: 0.2,
    22: 0.7,
    23: 1.4,
    24: 2.4,
    25: 3.4,
    26: 4.4,
    27: 7,
}

FLOOD_V2_DEPTHS = {1: 0.2, 2: 2, 3: 3.6, 4: 7, 5: 14, 6: 25}

TSUNAMI_DEPTHS = {
    "～ 0.3m未満": 0.1,
    "0.01m以上 ～ 0.3m未満": 0.1,
    "0.01m以上 0.3m未満": 0.1,
    "0.01m以上～0.3m未満": 0.1,
    "0.3m未満": 0.1,
    "0.3m以上 ～ 0.5m未満": 0.4,
    "0.3m以上 0.5m未満": 0.4,
    "0.3m以上 ～ 1m未満": 0.6,
    "0.3m以上～1m未満": 0.6,
    "0.5m以上 ～ 1m未満": 0.7,
    "0.5m以上 1.0m未満": 0.7,
    "1m以上 ～ 2m未満": 1.5,
    "1m以上～2m未満": 1.5,
    "1.0m以上 3.0m未満": 2,
    "1m以上 ～ 3m未満": 2,
    "2m以上 ～ 3m未満": 2.5,
    "2m以上～3m未満": 2.5,
    "2m以上 ～ 4m未満": 3,
    "2m以上 ～ 5m未満": 3.5,
    "3m以上 ～ 4m未満": 3.5,
    "3m以上～4m未満": 3.5,
    "3.0m以上 5.0m未満": 4,
    "3m以上 ～ 5m未満": 4,
    "4m以上 ～ 5m未満": 4.5,
    "4m以上～5m未満": 4.5,
    "4m以上": 6,
    "5.0m以上 10.0m未満": 7.5,
    "5m以上": 7.5,
    "5m以上 ～ 10m未満": 7.5,
    "5m以上～10m未満": 7.5,
    "10m以上 ～ 15m未満": 12.5,
    "10.0m以上 20.0m未満": 15,
    "10m以上": 15,
    "10m以上 ～ 20m未満": 15,
    "10m以上～20m未満": 15,
    "15m以上 ～ 20m未満": 17.5,
    "20.0m以上": 30,
    "20m以上": 30,
    "20m以上 ～ 50m未満": 35,
    "〜 0.3m未満": 0.1,
    "0.01m以上 〜 0.3m未満": 0.1,
    "0.01m以上〜0.3m未満": 0.1,
    "0.3m以上 〜 0.5m未満": 0.4,
    "0.3m以上 〜 1m未満": 0.6,
    "0.3m以上〜1m未満": 0.6,
    "0.5m以上 〜 1m未満": 0.7,
    "1m以上 〜 2m未満": 1.5,
    "1m以上〜2m未満": 1.5,
    "1m以上 〜 3m未満": 2,
    "2m以上 〜 3m未満": 2.5,
    "2m以上〜3m未満": 2.5,
    "2m以上 〜 4m未満": 3,
    "2m以上 〜 5m未満": 3.5,
    "3m以上 〜 4m未満": 3.5,
    "3m以上〜4m未満": 3.5,
    "3m以上 〜 5m未満": 4,
    "4m以上 〜 5m未満": 4.5,
    "4m以上〜5m未満": 4.5,
    "5m以上 〜 10m未満": 7.5,
    "5m以上〜10m未満": 7.5,
    "10m以上 〜 15m未満": 12.5,
    "10m以上 〜 20m未満": 15,
    "10m以上〜20m未満": 15,
    "15m以上 〜 20m未満": 17.5,
    "20m以上 〜 50m未満": 35,
}

STORM_SURGE_DEPTHS = {
    "0.3m未満": 0.1,
    "0.5m未満": 0.2,
    "0.3m以上0.5m未満": 0.4,
    "0.5m以上1m未満": 0.7,
    "0.5m以上3m未満": 2,
    "1m以上3m未満": 2,
    "3m以上5m未満": 4,
    "5m以上10m未満": 7.5,
    "10m以上20m未満": 15,
    "20m以上": 30,
}


class UnknownInundationCategoryError(ValueError):
    """入力データに変換表へ存在しない浸水区分がある。"""

    def __init__(self, hazard_name, field_name, unknown_counts):
        self.hazard_name = hazard_name
        self.field_name = field_name
        self.unknown_counts = dict(unknown_counts)
        details = "\n".join(
            f"・{value!r}: {count}件" for value, count in self.unknown_counts.items()
        )
        super().__init__(
            f"{hazard_name}の浸水区分（{field_name}）に未対応の値があります。\n"
            "0として処理せず停止しました。入力データまたは変換表を確認してください。\n"
            f"{details}"
        )


def _is_zero(value):
    if isinstance(value, Number):
        return value == 0
    return isinstance(value, str) and value.strip() in {"0", "0.0"}


def _matches_allowed(value, allowed_values):
    if value in allowed_values:
        return True
    if isinstance(value, str):
        try:
            numeric_value = float(value.strip())
        except ValueError:
            return False
        return numeric_value in allowed_values
    return False


def validate_categories(hazard_name, field_name, values, allowed_values):
    """NULLと0を許容し、それ以外の未対応値があれば件数付きで例外にする。"""

    unknown = Counter()
    for value in values:
        if value is None or _is_zero(value):
            continue
        if not _matches_allowed(value, allowed_values):
            unknown[str(value)] += 1

    if unknown:
        raise UnknownInundationCategoryError(
            hazard_name, field_name, sorted(unknown.items())
        )
