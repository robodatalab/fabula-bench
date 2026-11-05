import random
import unittest
from unittest.mock import Mock, call, patch

from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stages.concepts import DESCRIPTION_INSTRUCTIONS, AskForConceptsStep, DescribeConceptsStep


class AskForConceptsStepCall(unittest.TestCase):
    @patch("builtins.input", side_effect=["Motherhood", "War", ""])
    def test_the_concepts_typed_become_the_storys_concepts(self, _) -> None:
        document = Document("")
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)

        _, changed = AskForConceptsStep()(document, reviews, "")

        written = InteractiveAuthorStory(changed).written_concepts()
        self.assertEqual(written, "### Motherhood\n\n\n### War\n")


class DescribeConceptsStepCall(unittest.TestCase):
    # The author has the descriptions done again, then accepts the second.
    @patch("builtins.input", side_effect=["r", "say what it costs her", "a"])
    def test_describes_only_the_authors_concepts_again_with_the_authors_feedback_until_accepted(self, _) -> None:
        document = Document.from_cells([SalientConceptCell("Motherhood", [], "", False, None, "k1")])
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)
        model = Mock()
        model.complete.side_effect = [
            "### Motherhood\nA mother's care.",
            "### Motherhood\nA mother's care, at what it costs her.\n\n### Brutal father\nA father who rules by fear.",
        ]
        describe = DescribeConceptsStep(model)

        first_result, first_document = describe(document, reviews, "")
        _, second_document = describe(first_document, reviews, first_result.comment)

        self.assertEqual(first_result, ReviewResult.failed("say what it costs her"))
        self.assertEqual(
            model.complete.call_args_list,
            [
                call(DESCRIPTION_INSTRUCTIONS, "The author's concepts:\n### Motherhood\n", 1500),
                call(
                    DESCRIPTION_INSTRUCTIONS,
                    "The author's concepts:\n### Motherhood\n\n\nThe author asks you to do it again: say what it costs her",
                    1500,
                ),
            ],
        )
        written = InteractiveAuthorStory(second_document).written_concepts()
        self.assertEqual(written, "### Motherhood\nA mother's care, at what it costs her.")
