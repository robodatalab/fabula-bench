"""How well a model comprehended the salient concepts its play of a story showed
it.

Each concept is scored by how alike the model's explanation of it is to the
concept's abstract in meaning (embedding cosine), weighed by how little of the
concept the play showed — similarity × (1 − exposure) — so explaining a concept
the play only glimpsed counts for more than explaining one it showed in full.
The comprehension is the mean of those scores over the concepts.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Protocol

from authordoc.cells.salient_concept_cell import SalientConceptCell


class MeaningSimilarity(Protocol):
    """How alike abstracts and explanations are in meaning, one row per abstract;
    `DescriptionEmbedder` is one."""

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]: ...


def score_comprehension(
    concepts: Sequence[SalientConceptCell],
    exposures: Sequence[float],
    explanations: Sequence[str | None],
    meaning: MeaningSimilarity,
) -> float:
    """The mean, over the concepts, of how alike in meaning the model's explanation
    of each is to the concept's abstract, times 1 − the concept's exposure. A
    concept the model gave no explanation of is alike in nothing; with no
    concepts, nothing was comprehended, and the score is 0."""
    if not concepts:
        return 0.0
    abstracts = [concept.source for concept in concepts]
    answered = ["" if explanation is None else explanation for explanation in explanations]
    cosines = meaning.cosine_similarities(abstracts, answered)
    scores: list[float] = []
    for index, explanation in enumerate(explanations):
        cosine = 0.0 if explanation is None else cosines[index][index]
        score = cosine * (1 - exposures[index])
        scores.append(score)
    comprehension = statistics.fmean(scores)
    return comprehension
