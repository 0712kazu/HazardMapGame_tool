"""QGISに依存しないゲーム得点計算。"""

from .game_scores import (
    GameScores,
    HzdScores,
    calculate_game_scores,
    calculate_hzd,
    suggest_hzd_multiplier,
)
from .classification import (
    classify_standard_deviation_ranks,
    classify_tcg_ranks,
    ranks_to_percentages,
)

__all__ = [
    "GameScores",
    "HzdScores",
    "calculate_game_scores",
    "calculate_hzd",
    "suggest_hzd_multiplier",
    "classify_standard_deviation_ranks",
    "classify_tcg_ranks",
    "ranks_to_percentages",
]
