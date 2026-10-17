import unittest
from pathlib import Path

from fabula_bench import storydoc
from fabula_bench.labels import PLOT, LabelledConcept, labels_of
from fabula_bench.storydoc import Cell

STORIES = Path(__file__).parents[1] / "fabula_bench" / "stories"

# Story words: She(0) saw(1) the(2) door.(3) He(4) heard(5) the(6) bell.(7)
PROSE = storydoc.markdown("She saw the door. He heard the bell.")


def _document(*cells: Cell) -> storydoc.Document:
    text = storydoc.dumps([PROSE, *cells])
    document = storydoc.Document(text)
    return document


class Concepts(unittest.TestCase):
    def test_are_read_with_their_description_and_examples(self) -> None:
        concept = Cell(
            storydoc.SALIENT_CONCEPT, "What she saw.", {"title": "Door", "words": "0-3, 6-7"}
        )

        labels = labels_of(_document(concept))

        expected = LabelledConcept("Door", "What she saw.", ("She saw the door.", "the bell."))
        self.assertEqual(labels.concepts, (expected,))


class Plots(unittest.TestCase):
    def test_keep_their_spans_in_the_order_the_plot_gives_them(self) -> None:
        plot = Cell(PLOT, "The bell, then the door.", {"title": "Arrival", "words": "4-7, 0-3"})

        labels = labels_of(_document(plot))

        (arrival,) = labels.plots
        self.assertEqual(arrival.title, "Arrival")
        self.assertEqual(arrival.description, "The bell, then the door.")
        self.assertEqual(arrival.spans, ("He heard the bell.", "She saw the door."))

    def test_are_none_in_a_story_that_labels_none(self) -> None:
        concept = Cell(storydoc.SALIENT_CONCEPT, "What she saw.", {"title": "Door", "words": "0-3"})

        labels = labels_of(_document(concept))

        self.assertEqual(labels.plots, ())


class TheBenchmarkStories(unittest.TestCase):
    def test_label_every_concept_with_examples_and_every_plot_with_spans(self) -> None:
        story_paths = sorted(STORIES.glob(f"*{storydoc.EXTENSION}"))
        self.assertTrue(story_paths)
        for story_path in story_paths:
            with self.subTest(story=story_path.name):
                document = storydoc.Document.load(story_path)

                labels = labels_of(document)

                self.assertTrue(labels.concepts)
                for concept in labels.concepts:
                    self.assertTrue(concept.examples, concept.title)
                for plot in labels.plots:
                    self.assertTrue(plot.spans, plot.title)
