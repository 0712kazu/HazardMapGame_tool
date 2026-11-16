"""QGISに依存しないゲーム得点計算。"""

from .game_scores import (
    GameScores,
    HzdScores,
    calculate_game_scores,
    calculate_hzd,
    suggest_hzd_multiplier,
)

__all__ = [
    "GameScores",
    "HzdScores",
    "calculate_game_scores",
    "calculate_hzd",
    "suggest_hzd_multiplier",
]
