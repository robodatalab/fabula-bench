import unittest
from collections.abc import Sequence
from pathlib import Path

from fabula_bench.benchmark import AnsweredConcept, AnsweredPlot, StoryAnswers
from fabula_bench.labels import LabelledConcept, LabelledPlot, StoryLabels
from fabula_bench.scoring import (
    CONCEPTS,
    EXAMPLES,
    PLOTS,
    Counts,
    MeaningSimilarity,
    StoryScores,
    report,
    report_by_story,
    score,
    totals,
    trigram_similarity,
)

DOOR = LabelledConcept(
    "The door", "The front door she watches.", ("She saw the door.", "The door stood open.")
)
BELL = LabelledConcept("The bell", "The bell that rings at night.", ("He heard the bell.",))
ARRIVAL = LabelledPlot(
    "Arrival", "Someone arrives at the door.", ("He heard the bell.", "She saw the door.")
)


class _MeaningByTitle:
    """Stands in for the embedding model: two descriptions mean the same when
    they begin with the same title."""

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]:
        similarities = [
            [1.0 if _title(label) == _title(answer) else 0.0 for answer in answered]
            for label in labelled
        ]
        return similarities


class _MeaningAlwaysAlike:
    """Stands in for the embedding model: every two descriptions mean the same."""

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]:
        similarities = [[1.0 for _ in answered] for _ in labelled]
        return similarities


def _title(description: str) -> str:
    title, _, _ = description.partition(":")
    return title


def _story_scores(
    concepts: tuple[AnsweredConcept, ...] = (),
    plots: tuple[AnsweredPlot, ...] = (),
    labelled_concepts: tuple[LabelledConcept, ...] = (DOOR, BELL),
    labelled_plots: tuple[LabelledPlot, ...] = (),
    meaning: MeaningSimilarity | None = None,
) -> StoryScores:
    labels = StoryLabels(labelled_concepts, labelled_plots)
    story_answers = StoryAnswers(Path("door.author"), labels, concepts, plots, (), ())
    similarity = _MeaningByTitle() if meaning is None else meaning
    (story_scores,) = score([story_answers], similarity)
    return story_scores


class CountsMetrics(unittest.TestCase):
    def test_are_computed_from_the_three_counts(self) -> None:
        counts = Counts(true_positives=12, false_positives=3, false_negatives=5)

        self.assertAlmostEqual(counts.precision, 0.80)
        self.assertAlmostEqual(counts.recall, 12 / 17)
        self.assertAlmostEqual(counts.f1, 0.75)

    def test_are_none_where_there_is_nothing_to_divide_by(self) -> None:
        counts = Counts()

        self.assertIsNone(counts.precision)
        self.assertIsNone(counts.recall)
        self.assertIsNone(counts.f1)


class TrigramSimilarity(unittest.TestCase):
    def test_is_one_for_the_same_text_whatever_its_case_and_spacing(self) -> None:
        similarity = trigram_similarity("The  Front door", "the front DOOR")

        self.assertEqual(similarity, 1.0)

    def test_is_zero_for_texts_that_share_no_trigram(self) -> None:
        similarity = trigram_similarity("abc", "xyz")

        self.assertEqual(similarity, 0.0)


class ConceptScores(unittest.TestCase):
    def test_count_a_matched_concept_an_invented_one_and_a_missed_one(self) -> None:
        door = AnsweredConcept("The door", "The front door she keeps watching.", ())
        invented = AnsweredConcept("The cat", "A cat on the stairs.", ())

        story_scores = _story_scores(concepts=(door, invented))

        self.assertEqual(story_scores.counts[CONCEPTS], Counts(1, 1, 1))

    def test_count_a_concept_answered_twice_once(self) -> None:
        door = AnsweredConcept("The door", "The front door she keeps watching.", ())
        door_again = AnsweredConcept("The door", "The door at the front of the house.", ())

        story_scores = _story_scores(concepts=(door, door_again))

        self.assertEqual(story_scores.counts[CONCEPTS], Counts(1, 1, 1))

    def test_need_alike_wording_as_well_as_alike_meaning(self) -> None:
        unlike_wording = AnsweredConcept("Xyzzy", "Qwv jkp.", ())

        story_scores = _story_scores(
            concepts=(unlike_wording,), labelled_concepts=(DOOR,), meaning=_MeaningAlwaysAlike()
        )

        self.assertEqual(story_scores.counts[CONCEPTS], Counts(0, 1, 1))


class ExampleScores(unittest.TestCase):
    def test_compare_examples_with_those_of_the_matched_concept(self) -> None:
        door = AnsweredConcept(
            "The door",
            "The front door she keeps watching.",
            ("She saw the door.", "A cat sat on the stairs."),
        )

        story_scores = _story_scores(concepts=(door,), labelled_concepts=(DOOR,))

        self.assertEqual(story_scores.counts[EXAMPLES], Counts(1, 1, 1))

    def test_count_examples_of_unmatched_concepts_as_invented_or_missed(self) -> None:
        invented = AnsweredConcept("The cat", "A cat on the stairs.", ("The cat slept.",))

        story_scores = _story_scores(concepts=(invented,), labelled_concepts=(DOOR,))

        self.assertEqual(story_scores.counts[EXAMPLES], Counts(0, 1, 2))


class PlotScores(unittest.TestCase):
    def test_match_a_plot_whose_description_and_spans_both_match(self) -> None:
        arrival = AnsweredPlot(
            "Arrival",
            "Someone arrives at the front door.",
            ("He heard the bell.", "She saw the door."),
        )

        story_scores = _story_scores(plots=(arrival,), labelled_plots=(ARRIVAL,))

        self.assertEqual(story_scores.counts[PLOTS], Counts(1, 0, 0))

    def test_do_not_match_a_plot_whose_spans_come_in_another_order(self) -> None:
        reversed_arrival = AnsweredPlot(
            "Arrival",
            "Someone arrives at the front door.",
            ("She saw the door.", "He heard the bell."),
        )

        story_scores = _story_scores(plots=(reversed_arrival,), labelled_plots=(ARRIVAL,))

        self.assertEqual(story_scores.counts[PLOTS], Counts(0, 1, 1))


class Report(unittest.TestCase):
    def test_shows_the_counts_added_up_across_stories_and_no_story_alone(self) -> None:
        door = AnsweredConcept("The door", "The front door she keeps watching.", ())
        first = _story_scores(concepts=(door,))
        second = StoryScores(Path("bell.author"), first.counts)

        summed = totals([first, second])
        reported = report([first, second])

        self.assertEqual(summed[CONCEPTS], Counts(2, 0, 2))
        self.assertIn("All stories", reported)
        self.assertNotIn("door.author", reported)
        self.assertNotIn("bell.author", reported)

    def test_by_story_shows_every_story_and_no_totals(self) -> None:
        door = AnsweredConcept("The door", "The front door she keeps watching.", ())
        first = _story_scores(concepts=(door,))
        second = StoryScores(Path("bell.author"), first.counts)

        reported = report_by_story([first, second])

        self.assertIn("door.author", reported)
        self.assertIn("bell.author", reported)
        self.assertNotIn("All stories", reported)
