import unittest

from scoring.classification import (
    classify_standard_deviation_ranks,
    classify_tcg_ranks,
    ranks_to_percentages,
)


class TestClassification(unittest.TestCase):
    def test_tcg_keeps_zero_at_zero(self):
        self.assertEqual(classify_tcg_ranks([0, 0, 0]), [0, 0, 0])

    def test_tcg_default_preserves_current_six_rank_result(self):
        ranks = classify_tcg_ranks([0, 10, 255, 3598, 3699, 8555])

        self.assertEqual(ranks, [0, 1, 1, 2, 3, 5])

    def test_tcg_max_rank_is_configurable(self):
        ranks = classify_tcg_ranks(range(101), 4)

        self.assertEqual(max(ranks), 4)
        self.assertEqual(ranks[0], 0)

    def test_tcg_does_not_give_the_maximum_to_one_sparse_value(self):
        self.assertEqual(classify_tcg_ranks([0, 0, 100], 6), [0, 0, 5])

    def test_tcg_assigns_same_rank_to_same_values(self):
        ranks = classify_tcg_ranks([0, 2, 2, 10], 6)

        self.assertEqual(ranks[1], ranks[2])

    def test_standard_deviation_excludes_zero_from_statistics(self):
        ranks_with_many_zeros = classify_standard_deviation_ranks(
            [0, 0, 0, 10, 20, 30], 6
        )
        positive_only = classify_standard_deviation_ranks([10, 20, 30], 6)

        self.assertEqual(ranks_with_many_zeros[-3:], positive_only)
        self.assertEqual(ranks_with_many_zeros[:3], [0, 0, 0])

    def test_standard_deviation_equal_positive_values_are_rank_one(self):
        self.assertEqual(
            classify_standard_deviation_ranks([0, 5, 5], 6), [0, 1, 1]
        )

    def test_percentages_include_zero_and_maximum_boundaries(self):
        percentages = ranks_to_percentages([0, 1, 2], 2)

        self.assertAlmostEqual(percentages[0], 100 / 3)
        self.assertAlmostEqual(percentages[1], 200 / 3)
        self.assertEqual(percentages[2], 100)


if __name__ == "__main__":
    unittest.main()
