import unittest

from parameterized import parameterized

from fabula_bench.p80 import plot_spans_match, spans_match, words_of

LABELLED_EXAMPLE = "It is a beautiful day here in New York City"

FILLER = " ".join(["filler"] * 45)
PARAGRAPH_HOLDING_THE_EXAMPLE = f"{FILLER} {LABELLED_EXAMPLE} {FILLER}"

# Ten spans with no words in common, so that only their order and their number
# decide whether two plots match.
LABELLED_PLOT = [
    " ".join(f"span{index}word{letter}" for letter in "abcdefgh") for index in range(10)
]


class WordsOf(unittest.TestCase):
    def test_ignore_case_and_punctuation(self) -> None:
        words = words_of('"Seven lives!" she announced.')

        self.assertEqual(words, ["seven", "lives", "she", "announced"])

    def test_leave_out_punctuation_that_stands_alone(self) -> None:
        words = words_of("OKAFOR — KNOCK")

        self.assertEqual(words, ["okafor", "knock"])


class SpansMatch(unittest.TestCase):
    @parameterized.expand(
        [
            ("two_words_missing", "A beautiful day here in New York City", True),
            (
                "two_words_missing_and_two_added",
                "A beautiful day here in New York City for now.",
                True,
            ),
            (
                "two_words_missing_from_the_middle_and_the_end",
                "It is a beautiful day in New York",
                True,
            ),
            ("three_words_missing", "A beautiful day here in New York", False),
            ("the_example_inside_a_paragraph", PARAGRAPH_HOLDING_THE_EXAMPLE, False),
            ("the_same_words_out_of_order", "City York New in here day beautiful a is It", False),
        ]
    )
    def test_when_at_most_a_fifth_of_either_side_differs_in_order(
        self, _: str, answered: str, expected: bool
    ) -> None:
        matches = spans_match(LABELLED_EXAMPLE, answered)

        self.assertEqual(matches, expected)


class PlotSpansMatch(unittest.TestCase):
    @parameterized.expand(
        [
            ("every_span", LABELLED_PLOT, True),
            ("two_spans_missing", LABELLED_PLOT[:4] + LABELLED_PLOT[6:], True),
            ("three_spans_missing", LABELLED_PLOT[:4] + LABELLED_PLOT[7:], False),
            ("two_spans_added", LABELLED_PLOT + ["an added span", "another added span"], True),
            ("the_halves_swapped", LABELLED_PLOT[5:] + LABELLED_PLOT[:5], False),
            ("every_span_with_a_word_added", [f"{span} added" for span in LABELLED_PLOT], True),
        ]
    )
    def test_when_at_most_a_fifth_of_the_spans_differs_in_order(
        self, _: str, answered: list[str], expected: bool
    ) -> None:
        matches = plot_spans_match(LABELLED_PLOT, answered)

        self.assertEqual(matches, expected)
