"""Scoring: a model's answers against a story's labels, as true positives, false
positives and false negatives per task (README, "The tasks and how they are
measured" and "How the results are reported").

An answered concept or plot matches a labelled one when their descriptions —
title and description together — are alike both in meaning (embedding cosine)
and in wording (character-trigram overlap); a plot must also match the labelled
plot's spans at p80. Pairing is one-to-one, best-scoring pairs first: a labelled
concept is claimed at most once, so answering it twice gives one false positive.

An answered concept's examples are compared with the examples of the labelled
concept it was paired with. The examples of an answered concept that matched
nothing are false positives; the examples of a labelled concept that nothing
matched are false negatives.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from fabula_bench.benchmark import AnsweredConcept, AnsweredPlot, StoryAnswers
from fabula_bench.labels import LabelledConcept, LabelledPlot
from fabula_bench.p80 import plot_spans_match, spans_match

# Provisional, until they are calibrated against hand-marked answers.
LEAST_MEANING_SIMILARITY = 0.6
LEAST_WORDING_SIMILARITY = 0.1

TRIGRAM_LENGTH = 3

CONCEPTS = "salient concepts"
EXAMPLES = "examples"
PLOTS = "plots"
TASKS = (CONCEPTS, EXAMPLES, PLOTS)


class MeaningSimilarity(Protocol):
    """How alike labelled and answered descriptions are in meaning, one row per
    labelled description; `DescriptionEmbedder` is one."""

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]: ...


@dataclass(frozen=True)
class Counts:
    """True positives, false positives and false negatives of one task."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    def __add__(self, other: Counts) -> Counts:
        true_positives = self.true_positives + other.true_positives
        false_positives = self.false_positives + other.false_positives
        false_negatives = self.false_negatives + other.false_negatives
        summed = Counts(true_positives, false_positives, false_negatives)
        return summed

    @property
    def precision(self) -> float | None:
        """Of what the model said, how much was right; None when it said nothing."""
        said = self.true_positives + self.false_positives
        precision = None if said == 0 else self.true_positives / said
        return precision

    @property
    def recall(self) -> float | None:
        """Of what is labelled, how much the model found; None when nothing is labelled."""
        labelled = self.true_positives + self.false_negatives
        recall = None if labelled == 0 else self.true_positives / labelled
        return recall

    @property
    def f1(self) -> float | None:
        """Precision and recall balanced in one number; None when there is nothing to count."""
        counted = 2 * self.true_positives + self.false_positives + self.false_negatives
        f1 = None if counted == 0 else 2 * self.true_positives / counted
        return f1


@dataclass(frozen=True)
class StoryScores:
    """One story's counts, per task."""

    story: Path
    counts: dict[str, Counts]


def score(answers: Sequence[StoryAnswers], meaning: MeaningSimilarity) -> list[StoryScores]:
    """Each story's answers counted against its labels, task by task."""
    scores = [_story_scores(story_answers, meaning) for story_answers in answers]
    return scores


def totals(scores: Sequence[StoryScores]) -> dict[str, Counts]:
    """Each task's counts added up across all stories."""
    summed = {task: Counts() for task in TASKS}
    for story_scores in scores:
        for task in TASKS:
            summed[task] = summed[task] + story_scores.counts[task]
    return summed


def report(scores: Sequence[StoryScores]) -> str:
    """The totals, and below them the same table for each story."""
    summed = totals(scores)
    total_table = _table(summed)
    sections = [f"All stories\n{total_table}"]
    for story_scores in scores:
        story_table = _table(story_scores.counts)
        sections.append(f"{story_scores.story.name}\n{story_table}")
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


def _description_of(title: str, description: str) -> str:
    described = f"{title}: {description}"
    return described


LabelledT = TypeVar("LabelledT", LabelledConcept, LabelledPlot)
AnsweredT = TypeVar("AnsweredT", AnsweredConcept, AnsweredPlot)


def _paired(
    labelled: Sequence[LabelledT],
    answered: Sequence[AnsweredT],
    meaning: MeaningSimilarity,
    also_matches: Callable[[LabelledT, AnsweredT], bool],
) -> list[tuple[int, int]]:
    """One-to-one pairs of labelled and answered indices whose descriptions
    match, and which `also_matches` accepts, best-scoring pairs first."""
    if not labelled or not answered:
        return []
    labelled_descriptions = [_description_of(item.title, item.description) for item in labelled]
    answered_descriptions = [_description_of(item.title, item.description) for item in answered]
    cosines = meaning.cosine_similarities(labelled_descriptions, answered_descriptions)
    candidates: list[tuple[float, int, int]] = []
    for labelled_index, labelled_description in enumerate(labelled_descriptions):
        for answered_index, answered_description in enumerate(answered_descriptions):
            cosine = cosines[labelled_index][answered_index]
            wording = trigram_similarity(labelled_description, answered_description)
            descriptions_match = (
                cosine >= LEAST_MEANING_SIMILARITY and wording >= LEAST_WORDING_SIMILARITY
            )
            if not descriptions_match:
                continue
            labelled_item = labelled[labelled_index]
            answered_item = answered[answered_index]
            if not also_matches(labelled_item, answered_item):
                continue
            pair_score = cosine + wording
            candidate = (pair_score, labelled_index, answered_index)
            candidates.append(candidate)
    candidates.sort(reverse=True)
    pairs: list[tuple[int, int]] = []
    paired_labels: set[int] = set()
    paired_answers: set[int] = set()
    for _, labelled_index, answered_index in candidates:
        if labelled_index in paired_labels or answered_index in paired_answers:
            continue
        paired_labels.add(labelled_index)
        paired_answers.add(answered_index)
        pair = (labelled_index, answered_index)
        pairs.append(pair)
    return pairs


def _any_concepts(_labelled: LabelledConcept, _answered: AnsweredConcept) -> bool:
    return True


def _plot_spans(labelled: LabelledPlot, answered: AnsweredPlot) -> bool:
    spans_agree = plot_spans_match(labelled.spans, answered.spans)
    return spans_agree


def _counts_of_pairing(labelled_count: int, answered_count: int, pair_count: int) -> Counts:
    false_positives = answered_count - pair_count
    false_negatives = labelled_count - pair_count
    counts = Counts(pair_count, false_positives, false_negatives)
    return counts


def _example_counts(labelled_examples: Sequence[str], answered_examples: Sequence[str]) -> Counts:
    """Examples paired one-to-one at p80, each labelled example taking the first
    unpaired answered example that matches it."""
    paired_answers: set[int] = set()
    for labelled_example in labelled_examples:
        for answered_index, answered_example in enumerate(answered_examples):
            if answered_index in paired_answers:
                continue
            if spans_match(labelled_example, answered_example):
                paired_answers.add(answered_index)
                break
    labelled_count = len(labelled_examples)
    answered_count = len(answered_examples)
    pair_count = len(paired_answers)
    counts = _counts_of_pairing(labelled_count, answered_count, pair_count)
    return counts


def _story_scores(story_answers: StoryAnswers, meaning: MeaningSimilarity) -> StoryScores:
    concept_counts, example_counts = _concept_and_example_counts(story_answers, meaning)
    plot_counts = _plot_counts(story_answers, meaning)
    counts = {CONCEPTS: concept_counts, EXAMPLES: example_counts, PLOTS: plot_counts}
    story_scores = StoryScores(story_answers.story, counts)
    return story_scores


def _concept_and_example_counts(
    story_answers: StoryAnswers, meaning: MeaningSimilarity
) -> tuple[Counts, Counts]:
    labelled_concepts = story_answers.labels.concepts
    answered_concepts = story_answers.concepts
    concept_pairs = _paired(labelled_concepts, answered_concepts, meaning, _any_concepts)
    labelled_count = len(labelled_concepts)
    answered_count = len(answered_concepts)
    pair_count = len(concept_pairs)
    concept_counts = _counts_of_pairing(labelled_count, answered_count, pair_count)

    example_counts = Counts()
    for labelled_index, answered_index in concept_pairs:
        labelled_examples = labelled_concepts[labelled_index].examples
        answered_examples = answered_concepts[answered_index].examples
        pair_counts = _example_counts(labelled_examples, answered_examples)
        example_counts = example_counts + pair_counts
    paired_labels = {labelled_index for labelled_index, _ in concept_pairs}
    for labelled_index, labelled_concept in enumerate(labelled_concepts):
        if labelled_index not in paired_labels:
            missed_count = len(labelled_concept.examples)
            missed = Counts(false_negatives=missed_count)
            example_counts = example_counts + missed
    paired_answers = {answered_index for _, answered_index in concept_pairs}
    for answered_index, answered_concept in enumerate(answered_concepts):
        if answered_index not in paired_answers:
            invented_count = len(answered_concept.examples)
            invented = Counts(false_positives=invented_count)
            example_counts = example_counts + invented
    return concept_counts, example_counts


def _plot_counts(story_answers: StoryAnswers, meaning: MeaningSimilarity) -> Counts:
    labelled_plots = story_answers.labels.plots
    answered_plots = story_answers.plots
    plot_pairs = _paired(labelled_plots, answered_plots, meaning, _plot_spans)
    labelled_count = len(labelled_plots)
    answered_count = len(answered_plots)
    pair_count = len(plot_pairs)
    plot_counts = _counts_of_pairing(labelled_count, answered_count, pair_count)
    return plot_counts


def _formatted(value: float | None) -> str:
    formatted = "—" if value is None else f"{value:.2f}"
    return formatted


def _table(counts: dict[str, Counts]) -> str:
    header = f"{'task':<18}{'TP':>5}{'FP':>5}{'FN':>5}{'precision':>11}{'recall':>8}{'F1':>6}"
    rows = [header]
    for task in TASKS:
        task_counts = counts[task]
        precision = _formatted(task_counts.precision)
        recall = _formatted(task_counts.recall)
        f1 = _formatted(task_counts.f1)
        row = (
            f"{task:<18}{task_counts.true_positives:>5}{task_counts.false_positives:>5}"
            f"{task_counts.false_negatives:>5}{precision:>11}{recall:>8}{f1:>6}"
        )
        rows.append(row)
    table = "\n".join(rows)
    return table
