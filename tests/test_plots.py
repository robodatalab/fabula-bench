import random
import unittest
from unittest.mock import Mock, patch

from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stages.plots import ENDS_INSTRUCTIONS, IN_BETWEEN_INSTRUCTIONS, Plots


class PlotsRun(unittest.TestCase):
    # The author accepts every event shown.
    @patch("builtins.input", return_value="a")
    def test_the_events_between_the_ends_are_written_halfway_between_written_events(self, _) -> None:
        concept = SalientConceptCell("Motherhood", [], "A mother's care.", False, None, "k1")
        document = Document.from_cells([concept])
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)
        model = Mock()
        model.complete.side_effect = [
            "1 | earth, Varn's house | Varn learns she is pregnant.\n"
            "4 | mars, the base | Varn raises her son on Mars.",
            "2 | earth, Varn's house | Varn hides it from mission control.",
            "3 | mars, the base | Varn gives birth on Mars.",
        ]

        lay_out, ends, second_event, third_event = Plots(model).run(document)
        _, laid_out = lay_out(document, reviews, "")
        _, with_the_ends = ends(laid_out, reviews, "")
        _, with_the_second_event = second_event(with_the_ends, reviews, "")
        _, with_every_event = third_event(with_the_second_event, reviews, "")

        model.complete.assert_called_with(
            IN_BETWEEN_INSTRUCTIONS,
            "Motherhood: A mother's care.\n\n"
            "The event before:\n2 | earth, Varn's house | Varn hides it from mission control.\n\n"
            "The event after:\n4 | mars, the base | Varn raises her son on Mars.\n\n",
            300,
        )
        written = InteractiveAuthorStory(with_every_event).written_world_events("")
        self.assertEqual(
            written,
            "### Motherhood\n"
            "1 | earth, Varn's house | Varn learns she is pregnant.\n"
            "2 | earth, Varn's house | Varn hides it from mission control.\n"
            "3 | mars, the base | Varn gives birth on Mars.\n"
            "4 | mars, the base | Varn raises her son on Mars.",
        )
        (plot,) = with_every_event.plots()
        self.assertEqual(plot.concepts(with_every_event), [concept])


class PlotEndsStepCall(unittest.TestCase):
    # The author has the first ends done again, then accepts the second.
    @patch("builtins.input", side_effect=["r", "make it end in loss", "a"])
    def test_writes_the_ends_again_with_the_authors_feedback_until_the_author_accepts(self, _) -> None:
        concept = SalientConceptCell("Motherhood", [], "A mother's care.", False, None, "k1")
        document = Document.from_cells([concept])
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)
        model = Mock()
        model.complete.side_effect = [
            "1 | earth, Varn's house | Varn learns she is pregnant.\n"
            "4 | mars, the base | Varn raises her son on Mars.",
            "1 | earth, Varn's house | Varn learns she is pregnant.\n"
            "4 | mars, the base | Varn buries her son on Mars.",
        ]
        lay_out, ends, _, _ = Plots(model).run(document)
        _, laid_out = lay_out(document, reviews, "")

        first_result, _ = ends(laid_out, reviews, "")
        _, with_the_ends = ends(laid_out, reviews, first_result.comment)

        self.assertEqual(first_result, ReviewResult.failed("make it end in loss"))
        model.complete.assert_called_with(ENDS_INSTRUCTIONS, "Motherhood: A mother's care.\n\nmake it end in loss", 500)
        written = InteractiveAuthorStory(with_the_ends).written_world_events("")
        self.assertEqual(
            written,
            "### Motherhood\n"
            "1 | earth, Varn's house | Varn learns she is pregnant.\n"
            " |  | \n"
            " |  | \n"
            "4 | mars, the base | Varn buries her son on Mars.",
        )
