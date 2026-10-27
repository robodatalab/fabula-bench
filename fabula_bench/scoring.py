"""Scoring: how well a model explained the salient concepts its play of a story
showed it.

Each concept the play showed is scored twice: by how alike the model's explanation
is to the concept's abstract in meaning (embedding cosine), and in wording
(character-trigram overlap). Either similarity is weighed by how little of the
concept the play showed — score = similarity × (1 − exposure) — so explaining a
concept the play only glimpsed counts for more than explaining one it showed in
full. The final scores are the mean and the standard deviation of each over every
concept asked in every story.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fabula_bench.storydoc.cells.salient_concept_cell import SalientConceptCell

TRIGRAM_LENGTH = 3

COSINE = "cosine"
TRIGRAMS = "trigrams"
MEASURES = (COSINE, TRIGRAMS)


class MeaningSimilarity(Protocol):
    """How alike abstracts and explanations are in meaning, one row per abstract;
    `DescriptionEmbedder` is one."""

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]: ...


@dataclass(frozen=True)
class ConceptScore:
    """The model's explanation of one salient concept its play showed it — None
    when it gave none — and how alike it is to the concept's abstract."""

    title: str
    exposure: float
    explanation: str | None
    cosine: float
    trigrams: float

    @property
    def cosine_score(self) -> float:
        cosine_score = self.cosine * (1 - self.exposure)
        return cosine_score

    @property
    def trigram_score(self) -> float:
        trigram_score = self.trigrams * (1 - self.exposure)
        return trigram_score


@dataclass(frozen=True)
class StoryScores:
    """One story's concept scores, and what went wrong while it was played and asked."""

    story: Path
    concepts: tuple[ConceptScore, ...]
    problems: tuple[str, ...]


def score_concepts(
    concepts: Sequence[SalientConceptCell],
    exposures: Sequence[float],
    explanations: Sequence[str | None],
    meaning: MeaningSimilarity,
) -> list[ConceptScore]:
    """Each concept's explanation compared with the concept's abstract. A concept
    the model gave no explanation of is alike in nothing."""
    if not concepts:
        return []
    abstracts = [concept.source for concept in concepts]
    answered = ["" if explanation is None else explanation for explanation in explanations]
    cosines = meaning.cosine_similarities(abstracts, answered)
    concept_scores: list[ConceptScore] = []
    for index, concept in enumerate(concepts):
        explanation = explanations[index]
        if explanation is None:
            cosine = 0.0
            trigrams = 0.0
        else:
            cosine = cosines[index][index]
            trigrams = trigram_similarity(concept.source, explanation)
        concept_score = ConceptScore(concept.title, exposures[index], explanation, cosine, trigrams)
        concept_scores.append(concept_score)
    return concept_scores


def final_scores(scores: Sequence[StoryScores]) -> dict[str, tuple[float, float]]:
    """Each measure's mean and standard deviation over every concept asked in every
    story; empty when no concept was asked."""
    concept_scores = [concept for story_scores in scores for concept in story_scores.concepts]
    if not concept_scores:
        return {}
    cosine_scores = [concept.cosine_score for concept in concept_scores]
    trigram_scores = [concept.trigram_score for concept in concept_scores]
    cosine_final = _mean_and_std(cosine_scores)
    trigram_final = _mean_and_std(trigram_scores)
    finals = {COSINE: cosine_final, TRIGRAMS: trigram_final}
    return finals


def report(scores: Sequence[StoryScores]) -> str:
    """The final scores, under how many concepts they were taken over."""
    finals = final_scores(scores)
    concept_count = sum(len(story_scores.concepts) for story_scores in scores)
    rows = [f"All stories: {concept_count} concepts asked", f"{'measure':<10}{'mean':>8}{'std':>8}"]
    for measure, (mean, std) in finals.items():
        row = f"{measure:<10}{mean:>8.3f}{std:>8.3f}"
        rows.append(row)
    reported = "\n".join(rows)
    return reported


def report_by_story(scores: Sequence[StoryScores]) -> str:
    """Every story's concepts — exposure, similarities and scores — then the
    model's explanations, and what went wrong."""
    sections: list[str] = []
    for story_scores in scores:
        header = (
            f"{'concept':<32}{'exposure':>9}{'cosine':>8}{'trigrams':>9}"
            f"{'cosine score':>14}{'trigram score':>15}"
        )
        rows = [story_scores.story.name, header]
        for concept in story_scores.concepts:
            row = (
                f"{concept.title[:31]:<32}{concept.exposure:>9.0%}{concept.cosine:>8.3f}"
                f"{concept.trigrams:>9.3f}{concept.cosine_score:>14.3f}{concept.trigram_score:>15.3f}"
            )
            rows.append(row)
        for concept in story_scores.concepts:
            rows.append(f"\n{concept.title}: {concept.explanation}")
        for problem in story_scores.problems:
            rows.append(f"\nproblem: {problem}")
        section = "\n".join(rows)
        sections.append(section)
    reported = "\n\n".join(sections)
    return reported


def trigram_similarity(first: str, second: str) -> float:
    """The Jaccard overlap of the two texts' character trigrams, ignoring case
    and runs of whitespace."""
    first_trigrams = _trigrams_of(first)
    second_trigrams = _trigrams_of(second)
    union = first_trigrams | second_trigrams
    if not union:
        return 0.0
    shared = first_trigrams & second_trigrams
    similarity = len(shared) / len(union)
    return similarity


def _trigrams_of(text: str) -> set[str]:
    lowered = text.lower()
    words = lowered.split()
    normalised = " ".join(words)
    last_start = len(normalised) - TRIGRAM_LENGTH + 1
    trigrams = {normalised[start : start + TRIGRAM_LENGTH] for start in range(last_start)}
    return trigrams


def _mean_and_std(values: Sequence[float]) -> tuple[float, float]:
    mean = statistics.fmean(values)
    std = statistics.pstdev(values)
    return (mean, std)
