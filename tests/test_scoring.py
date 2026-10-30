import unittest
from collections.abc import Sequence

from authordoc.cells.salient_concept_cell import SalientConceptCell

from fabula_bench.metrics.salient_concept_comprehension import score_comprehension

HOME = SalientConceptCell(title="Home", references=[], source="Where one belongs.")
WAR = SalientConceptCell(title="War", references=[], source="Conflict between peoples.")


class _AlikeInEverything:
    """Stands in for the embedder: every explanation is alike to every abstract."""

    def cosine_similarities(self, labelled: Sequence[str], answered: Sequence[str]) -> list[list[float]]:
        return [[1.0 for _ in answered] for _ in labelled]


class ScoreComprehension(unittest.TestCase):
    def test_is_the_mean_similarity_weighed_by_how_little_of_each_concept_was_shown(self) -> None:
        meaning = _AlikeInEverything()

        comprehension = score_comprehension([HOME, WAR], [0.5, 0.0], ["A place.", "A fight."], meaning)

        self.assertEqual(comprehension, 0.75)

    def test_counts_a_concept_without_an_explanation_as_alike_in_nothing(self) -> None:
        meaning = _AlikeInEverything()

        comprehension = score_comprehension([HOME, WAR], [0.0, 0.0], ["A place.", None], meaning)

        self.assertEqual(comprehension, 0.5)

    def test_is_zero_with_no_concepts(self) -> None:
        meaning = _AlikeInEverything()

        comprehension = score_comprehension([], [], [], meaning)

        self.assertEqual(comprehension, 0.0)
