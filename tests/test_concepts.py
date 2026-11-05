import random
import unittest
from unittest.mock import Mock, call, patch

from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stages.concepts import GENERATION_INSTRUCTIONS, AskForConceptsStep, GenerateConceptsStep


class AskForConceptsStepCall(unittest.TestCase):
    @patch("builtins.input", side_effect=["Motherhood", "War", ""])
    def test_the_concepts_typed_become_the_storys_concepts(self, _) -> None:
        document = Document("")
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)

        _, changed = AskForConceptsStep()(document, reviews, "")

        written = InteractiveAuthorStory(changed).written_concepts()
        self.assertEqual(written, "### Motherhood\n\n\n### War\n")


class GenerateConceptsStepCall(unittest.TestCase):
    # The author has the first concepts done again, then accepts the second.
    @patch("builtins.input", side_effect=["r", "make the father brutal, add social help", "a"])
    def test_generates_again_with_the_authors_feedback_until_the_author_accepts(self, _) -> None:
        document = Document.from_cells([SalientConceptCell("Motherhood", [], "", False, None, "k1")])
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)
        model = Mock()
        model.complete.side_effect = [
            "### Motherhood\nA mother's care.\n\n### Father\nA father.",
            "### Motherhood\nA mother's care.\n\n### Brutal father\nA father who rules by fear.\n\n### Social help\nThe help a community gives.",
        ]
        generate = GenerateConceptsStep(model)

        first_result, first_document = generate(document, reviews, "")
        _, second_document = generate(first_document, reviews, first_result.comment)

        self.assertEqual(first_result, ReviewResult.failed("make the father brutal, add social help"))
        self.assertEqual(
            model.complete.call_args_list,
            [
                call(GENERATION_INSTRUCTIONS, "The concepts so far:\n### Motherhood\n", 1500),
                call(
                    GENERATION_INSTRUCTIONS,
                    "The concepts so far:\n### Motherhood\n\n\nThe author asks you to do it again: make the father brutal, add social help",
                    1500,
                ),
            ],
        )
        written = InteractiveAuthorStory(second_document).written_concepts()
        self.assertEqual(
            written,
            "### Motherhood\nA mother's care.\n\n"
            "### Brutal father\nA father who rules by fear.\n\n"
            "### Social help\nThe help a community gives.",
        )
