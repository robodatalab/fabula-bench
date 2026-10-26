"""The labels a story's answers are scored against, read from its `.author` file.

- A salient concept is a `salient-concept` cell: its title, its description (the
  cell's text), and its examples (the story-word ranges in `words`).
- A plot is a `plot` cell: its title, its description, and the spans that form
  it (the story-word ranges of its `nodes`), in the order the plot gives them.
"""

from __future__ import annotations

from dataclasses import dataclass

from fabula_bench.storydoc.cells.plot_cell import PlotCell
from fabula_bench.storydoc.cells.salient_concept_cell import SalientConceptCell
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document


@dataclass(frozen=True)
class LabelledConcept:
    title: str
    description: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class LabelledPlot:
    title: str
    description: str
    # In the order the plot gives them: copied out in this order, they read as
    # a substory.
    spans: tuple[str, ...]


@dataclass(frozen=True)
class StoryLabels:
    concepts: tuple[LabelledConcept, ...]
    plots: tuple[LabelledPlot, ...]


def labels_of(document: Document) -> StoryLabels:
    story_words = StoryWordsIterator(document)
    concept_cells = document.salient_concepts()
    concepts = [_labelled_concept(cell, story_words) for cell in concept_cells]
    plot_cells = document.plots()
    plots = [_labelled_plot(cell, story_words) for cell in plot_cells]
    concepts_of_the_story = tuple(concepts)
    plots_of_the_story = tuple(plots)
    labels = StoryLabels(concepts_of_the_story, plots_of_the_story)
    return labels


def _labelled_concept(cell: SalientConceptCell, story_words: StoryWordsIterator) -> LabelledConcept:
    examples = [story_words.text(reference.story_word_range) for reference in cell.references]
    examples_in_order = tuple(examples)
    concept = LabelledConcept(cell.title, cell.source, examples_in_order)
    return concept


def _labelled_plot(cell: PlotCell, story_words: StoryWordsIterator) -> LabelledPlot:
    spans = [story_words.text(node.story_word_range) for node in cell.nodes]
    spans_in_order = tuple(spans)
    plot = LabelledPlot(cell.title, cell.source, spans_in_order)
    return plot
