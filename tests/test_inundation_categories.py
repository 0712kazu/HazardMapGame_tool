import pytest

from converter.inundation_categories import (
    FLOOD_V1_DEPTHS,
    STORM_SURGE_DEPTHS,
    TSUNAMI_DEPTHS,
    UnknownInundationCategoryError,
    validate_categories,
)


def test_known_categories_zero_and_null_are_accepted():
    validate_categories(
        "津波",
        "A40_003",
        [None, 0, 0.0, "0", "0.0", "0.3m未満", "20m以上 ～ 50m未満"],
        TSUNAMI_DEPTHS.keys(),
    )


def test_numeric_flood_category_strings_are_accepted():
    validate_categories("洪水", "A31_001", [11, "12", "27"], FLOOD_V1_DEPTHS.keys())


def test_unknown_categories_stop_processing_with_counts():
    with pytest.raises(UnknownInundationCategoryError) as error:
        validate_categories(
            "高潮", "A49_003", ["50m以上", "50m以上", "区分不明"], STORM_SURGE_DEPTHS.keys(),
        )

    message = str(error.value)
    assert "0として処理せず停止しました" in message
    assert "'50m以上': 2件" in message
    assert "'区分不明': 1件" in message


def test_blank_category_is_not_treated_as_zero():
    with pytest.raises(UnknownInundationCategoryError):
        validate_categories("津波", "A40_003", [""], TSUNAMI_DEPTHS.keys())
