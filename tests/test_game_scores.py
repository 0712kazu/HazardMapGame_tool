import unittest

from scoring.game_scores import (
    calculate_game_scores,
    calculate_hzd,
    suggest_hzd_multiplier,
)


class TestGameScores(unittest.TestCase):
    def test_zero_scores_stay_zero(self):
        result = calculate_game_scores([0], [0], [0], [0])

        self.assertEqual(result.a33, (0,))
        self.assertEqual(result.base_hzd, (0,))
        self.assertEqual(result.hzd, (0,))
        self.assertEqual(result.hzd_multiplier, 1.0)

    def test_a33_is_scaled_proportionally_to_six_and_rounded_up(self):
        result = calculate_game_scores(
            [0, 0, 0],
            [0, 2, 6],
            [0, 2, 6],
            [0, 0, 0],
            hzd_multiplier=1,
        )

        self.assertEqual(result.a33, (0, 2, 6))

    def test_a33_is_not_scaled_when_maximum_is_six_or_less(self):
        result = calculate_game_scores(
            [0, 0], [0, 3], [0, 3], [0, 0], hzd_multiplier=1
        )

        self.assertEqual(result.a33, (0, 6))

    def test_auto_multiplier_raises_maximum_to_fifteen(self):
        result = calculate_game_scores(
            [0, 2], [0, 1], [0, 1], [0, 1]
        )

        self.assertEqual(result.base_hzd, (0, 5))
        self.assertEqual(result.hzd_multiplier, 3.0)
        self.assertEqual(result.hzd, (0, 15))

    def test_manual_multiplier_allows_scores_over_sixteen(self):
        result = calculate_game_scores(
            [0, 6], [0, 3], [0, 3], [0, 6], hzd_multiplier=2
        )

        self.assertEqual(result.base_hzd, (0, 18))
        self.assertEqual(result.hzd, (0, 36))

    def test_recalculation_keeps_the_user_multiplier(self):
        first = calculate_game_scores(
            [1], [1], [0], [1], hzd_multiplier=2.5
        )
        recalculated = calculate_game_scores(
            [2], [1], [0], [1], hzd_multiplier=first.hzd_multiplier
        )

        self.assertEqual(first.hzd_multiplier, 2.5)
        self.assertEqual(recalculated.hzd_multiplier, 2.5)
        self.assertEqual(recalculated.hzd, (10,))

    def test_total_score_is_rounded_up_after_multiplication(self):
        result = calculate_game_scores(
            [1], [0], [0], [0], hzd_multiplier=1.01
        )

        self.assertEqual(result.hzd, (2,))

    def test_suggested_multiplier_never_reduces_scores(self):
        self.assertEqual(suggest_hzd_multiplier([0, 16]), 1.0)

    def test_future_hazard_can_be_added_to_total_without_changing_game_fields(self):
        totals = calculate_hzd(
            {"A31": [1], "A33": [2], "A40": [3], "earthquake": [4]},
            multiplier=1,
        )

        self.assertEqual(totals.base_hzd, (10,))
        self.assertEqual(totals.hzd, (10,))

    def test_mesh_counts_must_match(self):
        with self.assertRaisesRegex(ValueError, "メッシュ数"):
            calculate_game_scores([1], [1, 2], [0], [0])

    def test_negative_scores_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "負の点数"):
            calculate_game_scores([-1], [0], [0], [0])


if __name__ == "__main__":
    unittest.main()
