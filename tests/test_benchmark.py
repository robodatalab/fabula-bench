import json
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from fabula_bench import storydoc
from fabula_bench.benchmark import AnsweredConcept, AnsweredPlot, evaluate
from fabula_bench.labels import PLOT
from fabula_bench.models.base import Model, Turn
from fabula_bench.storydoc import Cell

PROSE = "She saw the door. He heard the bell."
CONCEPT = Cell(storydoc.SALIENT_CONCEPT, "What she saw.", {"title": "Door", "words": "0-3"})
PLOT_CELL = Cell(PLOT, "The bell, then the door.", {"title": "Arrival", "words": "4-7, 0-3"})

CONCEPTS_REPLY = json.dumps(
    {
        "concepts": [
            {
                "title": "The door",
                "description": "What she sees.",
                "examples": ["She saw the door."],
            }
        ]
    }
)
PLOTS_REPLY = json.dumps(
    {"plots": [{"title": "Arrival", "description": "A bell.", "spans": ["He heard the bell."]}]}
)


class _ScriptedModel(Model):
    """Replies to a question for concepts with `concepts_reply`, and to one for
    plots with `plots_reply`, and keeps every conversation it was given."""

    def __init__(
        self, concepts_reply: str | None = CONCEPTS_REPLY, plots_reply: str | None = PLOTS_REPLY
    ) -> None:
        self.concepts_reply = concepts_reply
        self.plots_reply = plots_reply
        self.conversations: list[Sequence[Turn]] = []

    def generate(self, conversations: Sequence[Sequence[Turn]]) -> list[str | None]:
        self.conversations.extend(conversations)
        replies = [
            self.plots_reply
            if "plots of the story" in conversation[0].text
            else self.concepts_reply
            for conversation in conversations
        ]
        return replies


class Evaluate(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.stories = Path(directory.name)

    def _write_story(self, name: str, *labels: Cell) -> Path:
        story_path = self.stories / f"{name}{storydoc.EXTENSION}"
        prose = storydoc.markdown(PROSE)
        storydoc.save(story_path, [prose, *labels])
        return story_path

    def test_gives_the_model_the_prose_and_none_of_the_labels(self) -> None:
        self._write_story("door", CONCEPT, PLOT_CELL)
        model = _ScriptedModel()

        evaluate(model, self.stories)

        for conversation in model.conversations:
            (turn,) = conversation
            self.assertIn(f"<story>\n{PROSE}\n</story>", turn.text)
            self.assertNotIn("What she saw.", turn.text)
            self.assertNotIn("The bell, then the door.", turn.text)

    def test_reads_the_answers_into_the_shape_of_the_labels(self) -> None:
        story_path = self._write_story("door", CONCEPT, PLOT_CELL)

        (story_answers,) = evaluate(_ScriptedModel(), self.stories)

        self.assertEqual(story_answers.story, story_path)
        self.assertEqual(story_answers.labels.concepts[0].title, "Door")
        concept = AnsweredConcept("The door", "What she sees.", ("She saw the door.",))
        plot = AnsweredPlot("Arrival", "A bell.", ("He heard the bell.",))
        self.assertEqual(story_answers.concepts, (concept,))
        self.assertEqual(story_answers.plots, (plot,))
        self.assertEqual(story_answers.problems, ())

    def test_asks_only_the_tasks_a_story_has_labels_for(self) -> None:
        self._write_story("concepts_only", CONCEPT)
        self._write_story("unlabelled")
        model = _ScriptedModel()

        answers = evaluate(model, self.stories)

        (story_answers,) = answers
        self.assertEqual(story_answers.story.name, "concepts_only.author")
        self.assertEqual(len(model.conversations), 1)
        self.assertEqual(story_answers.plots, ())

    def test_reads_an_answer_from_a_code_fence_with_words_around_it(self) -> None:
        self._write_story("door", CONCEPT)
        fenced_reply = f"Here they are:\n```json\n{CONCEPTS_REPLY}\n```\nI hope this helps."

        (story_answers,) = evaluate(_ScriptedModel(concepts_reply=fenced_reply), self.stories)

        self.assertEqual(story_answers.concepts[0].title, "The door")

    def test_keeps_a_reply_it_cannot_read_and_says_why(self) -> None:
        self._write_story("door", CONCEPT)

        with self.assertLogs("fabula_bench.benchmark", level="WARNING") as logged:
            (story_answers,) = evaluate(
                _ScriptedModel(concepts_reply="I'd rather not."), self.stories
            )

        self.assertEqual(story_answers.concepts, ())
        self.assertEqual(story_answers.replies, ("I'd rather not.",))
        self.assertEqual(story_answers.problems, ("the concepts reply holds no JSON object",))
        self.assertIn("door.author: the concepts reply holds no JSON object", logged.output[0])

    def test_goes_on_past_a_question_the_model_gave_no_reply_to(self) -> None:
        self._write_story("door", CONCEPT, PLOT_CELL)

        with self.assertLogs("fabula_bench.benchmark", level="WARNING") as logged:
            (story_answers,) = evaluate(_ScriptedModel(concepts_reply=None), self.stories)

        self.assertEqual(story_answers.concepts, ())
        self.assertEqual(story_answers.plots[0].title, "Arrival")
        self.assertEqual(story_answers.problems, ("the model gave no concepts reply",))
        self.assertIn("door.author: the model gave no concepts reply", logged.output[0])

    def test_leaves_out_an_entry_not_in_the_asked_shape(self) -> None:
        self._write_story("door", CONCEPT)
        reply = json.dumps(
            {
                "concepts": [
                    {
                        "title": "The door",
                        "description": "What she sees.",
                        "examples": ["She saw the door."],
                    },
                    {"title": "The bell"},
                ]
            }
        )

        (story_answers,) = evaluate(_ScriptedModel(concepts_reply=reply), self.stories)

        concept_titles = [concept.title for concept in story_answers.concepts]
        self.assertEqual(concept_titles, ["The door"])
        (problem,) = story_answers.problems
        self.assertIn("left out a concepts entry", problem)
