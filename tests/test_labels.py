import unittest
from pathlib import Path

from fabula_bench.labels import LabelledConcept, labels_of
from fabula_bench.storydoc.cells.cell import Cell
from fabula_bench.storydoc.cells.markdown_cell import MarkdownCell
from fabula_bench.storydoc.cells.plot_cell import PlotCell, PlotNode
from fabula_bench.storydoc.cells.salient_concept_cell import SalientConceptCell
from fabula_bench.storydoc.cells.story_word_range import StoryWordRange
from fabula_bench.storydoc.storydoc import EXTENSION, Document

STORIES = Path(__file__).parents[1] / "fabula_bench" / "stories"

# Story words: She(0) saw(1) the(2) door.(3) He(4) heard(5) the(6) bell.(7)
PROSE = MarkdownCell("She saw the door. He heard the bell.")


def _document(*cells: Cell) -> Document:
    document = Document.from_cells([PROSE, *cells])
    return document


class Concepts(unittest.TestCase):
    def test_are_read_with_their_description_and_examples(self) -> None:
        concept = SalientConceptCell(
            title="Door",
            story_word_ranges=[StoryWordRange(0, 3), StoryWordRange(6, 7)],
            source="What she saw.",
        )

        labels = labels_of(_document(concept))

        expected = LabelledConcept("Door", "What she saw.", ("She saw the door.", "the bell."))
        self.assertEqual(labels.concepts, (expected,))


class Plots(unittest.TestCase):
    def test_keep_their_spans_in_the_order_the_plot_gives_them(self) -> None:
        plot = PlotCell(
            title="Arrival",
            nodes=[PlotNode("n1", StoryWordRange(4, 7)), PlotNode("n2", StoryWordRange(0, 3))],
            source="The bell, then the door.",
        )

        labels = labels_of(_document(plot))

        (arrival,) = labels.plots
        self.assertEqual(arrival.title, "Arrival")
        self.assertEqual(arrival.description, "The bell, then the door.")
        self.assertEqual(arrival.spans, ("He heard the bell.", "She saw the door."))

    def test_are_none_in_a_story_that_labels_none(self) -> None:
        concept = SalientConceptCell(
            title="Door", story_word_ranges=[StoryWordRange(0, 3)], source="What she saw."
        )

        labels = labels_of(_document(concept))

        self.assertEqual(labels.plots, ())


class TheBenchmarkStories(unittest.TestCase):
    def test_label_every_concept_with_examples_and_every_plot_with_spans(self) -> None:
        story_paths = sorted(STORIES.glob(f"*{EXTENSION}"))
        self.assertTrue(story_paths)
        for story_path in story_paths:
            with self.subTest(story=story_path.name):
                document = Document.load(story_path)

                labels = labels_of(document)

                self.assertTrue(labels.concepts)
                for concept in labels.concepts:
                    self.assertTrue(concept.examples, concept.title)
                for plot in labels.plots:
                    self.assertTrue(plot.spans, plot.title)
