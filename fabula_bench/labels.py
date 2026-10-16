"""The labels a story's answers are scored against, read from its `.author` file.

- A salient concept is a `salient-concept` cell: its title, its description (the
  cell's text), and its examples (the story-word ranges in `words`).
- A plot is a `plot` cell, written the same way, whose `words` ranges are the
  spans that form it, in the order the plot gives them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from fabula_bench import storydoc

PLOT = "plot"


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


def labels_of(document: storydoc.Document) -> StoryLabels:
    concept_cells = _cells_of_kind(document, storydoc.SALIENT_CONCEPT)
    concepts_in_the_story = document.salient_concepts()
    concepts = [
        _labelled_concept(cell, concept_in_the_story)
        for cell, concept_in_the_story in zip(concept_cells, concepts_in_the_story, strict=True)
    ]
    plots = _labelled_plots_in(document)
    labels = StoryLabels(tuple(concepts), plots)
    return labels


def _cells_of_kind(document: storydoc.Document, kind: str) -> list[storydoc.Cell]:
    cells = [cell for cell in document.cells if cell.kind == kind]
    return cells


def _texts_of(concept_in_the_story: storydoc.SalientConceptInTheStory) -> tuple[str, ...]:
    texts = [word_range.text for word_range in concept_in_the_story.story_word_ranges]
    texts_in_order = tuple(texts)
    return texts_in_order


def _labelled_concept(
    cell: storydoc.Cell, concept_in_the_story: storydoc.SalientConceptInTheStory
) -> LabelledConcept:
    examples = _texts_of(concept_in_the_story)
    concept = LabelledConcept(cell.title, cell.source, examples)
    return concept


def _labelled_plots_in(document: storydoc.Document) -> tuple[LabelledPlot, ...]:
    # `storydoc` reads story-word ranges only for salient-concept cells. A plot
    # is a salient concept whose ranges are ordered, so its ranges are read by
    # the same code, through a document holding the prose and each plot written
    # as a salient concept. The prose is unchanged, so every word keeps its index.
    plot_cells = _cells_of_kind(document, PLOT)
    plots_as_concepts = [replace(cell, kind=storydoc.SALIENT_CONCEPT) for cell in plot_cells]
    markdown_cells = document.markdown_cells()
    prose_and_plots = storydoc.dumps(markdown_cells + plots_as_concepts)
    reading = storydoc.Document(prose_and_plots)
    plots_in_the_story = reading.salient_concepts()
    plots: list[LabelledPlot] = []
    for cell, plot_in_the_story in zip(plot_cells, plots_in_the_story, strict=True):
        spans = _texts_of(plot_in_the_story)
        plot = LabelledPlot(cell.title, cell.source, spans)
        plots.append(plot)
    plots_of_the_story = tuple(plots)
    return plots_of_the_story
