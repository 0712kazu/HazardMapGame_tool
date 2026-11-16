import unittest

from scoring.score_summary import format_score_summary, summarize_scores


class TestScoreSummary(unittest.TestCase):
    def test_summarizes_zero_and_positive_scores(self):
        summary = summarize_scores(
            {
                "A31": [0, 1, 3, 6],
                "HZD": [0, 4, 10, 18],
            }
        )

        a31 = summary.fields["A31"]
        self.assertEqual(a31.minimum, 0)
        self.assertEqual(a31.maximum, 6)
        self.assertEqual(a31.average, 2.5)
        self.assertEqual(a31.zero_count, 1)
        self.assertEqual(a31.distribution, ((0, 1), (1, 1), (3, 1), (6, 1)))

    def test_formats_hzd_distribution(self):
        text = format_score_summary(
            summarize_scores({"A31": [0, 1], "HZD": [0, 18]})
        )

        self.assertIn("洪水: 0 / 1 / 0.5 / 1件", text)
        self.assertIn("総合得点: 0 / 18 / 9.0 / 1件", text)
        self.assertIn("総合得点の点数別件数", text)
        self.assertIn("0点:1件 / 18点:1件", text)

    def test_rejects_non_integer_scores(self):
        with self.assertRaisesRegex(ValueError, "0以上の整数"):
            summarize_scores({"HZD": [1.5]})


if __name__ == "__main__":
    unittest.main()
