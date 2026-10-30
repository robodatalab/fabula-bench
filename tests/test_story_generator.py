"""These run the whole workflow, with a model and an author standing in for the
real ones, on stories written into temporary directories."""

import logging
import tempfile
import unittest
from pathlib import Path

from authordoc.cells.note_cell import NoteCell
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices
from story_generator.stage_visitor import Review, StageVisitor, Verdict
from story_generator.stages import annotations, choices, concepts, high_level_plots, low_level_plots, meeting_points, scenes
from story_generator.stages.annotations import Annotations, get_scene_cells
from story_generator.stages.choices import Choices
from story_generator.stages.concepts import Concepts
from story_generator.stages.high_level_plots import HighLevelPlots
from story_generator.stages.low_level_plots import LowLevelPlots
from story_generator.stages.meeting_points import MeetingPoints
from story_generator.stages.plot_ideas import PlotIdeas
from story_generator.stages.scenes import Scenes
from story_generator.workflow import Workflow, get_checkpoint

ACCEPT = Review(Verdict.ACCEPT)
STOP = Review(Verdict.STOP)
STAGES_IN_ORDER = [
    "plot ideas",
    "high-level plots",
    "low-level plots",
    "meeting points",
    "scenes",
    "choices",
    "concepts",
    "annotations",
]
# The author adds one idea, and accepts it.
AN_IDEA = {"plot ideas": [Review(Verdict.REVISE, "A heist."), ACCEPT]}


def _between(text: str, start: str, end: str = "\n\n") -> str:
    """The text after the first `start`, up to the `end` that follows it."""
    _, _, after = text.partition(start)
    found, _, _ = after.partition(end)
    return found


class _Model:
    """Stands in for the model. An outline is the idea, said back, with the
    author's latest comment as its last act; a plot is its beginning and its end
    in one house; the meeting points leave the events as they were; a scene is
    what happens in it, said back; every choice is "Then, it went on."; and a
    concept's passage is the first scene, from its first word to its last. It
    remembers what it was asked for."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        if system == high_level_plots.INSTRUCTIONS:
            self.asked.append("outline")
            idea = _between(user, "The author's idea:\n")
            outline = f"## {idea}\n\nWhat {idea} is about.\n\n1. It begins."
            if "The author's comments" not in user:
                return outline
            comments = _between(user, "The author's comments, oldest first:\n", "\n\n\n")
            lines = comments.splitlines()
            latest = lines[-1]
            comment = latest.removeprefix("- ")
            return f"{outline}\n2. {comment}"
        if system == low_level_plots.INSTRUCTIONS:
            self.asked.append("events")
            title = _between(user, "The plot's outline:\n## ", "\n")
            return f"1.1 | earth, a house | {title} begins.\n1.2 | earth, a house | {title} ends."
        if system == meeting_points.INSTRUCTIONS:
            self.asked.append("meeting points")
            _, _, after = user.partition("The plot to revise, ")
            _, _, events = after.partition(":\n")
            plot_events, _, _ = events.partition("\n\nYour draft")
            return plot_events
        if system == concepts.INSTRUCTIONS:
            self.asked.append("concepts")
            return (
                "## General\n\n### Home\nWhere one belongs.\n\n"
                "## Story-specific\n\n### The way back\nWhat the plot builds up to."
            )
        if system == scenes.INSTRUCTIONS:
            self.asked.append("scene")
            happening = _between(user, "What happens there:\n")
            scene = happening.replace("- ", "")
            return scene
        if system == choices.OPENING_INSTRUCTIONS:
            self.asked.append("opening")
            return "Then,"
        if system == choices.ENDING_INSTRUCTIONS:
            self.asked.append("ending")
            return "it went on."
        if system == annotations.INSTRUCTIONS:
            self.asked.append("passages")
            first_scene = _between(user, "S1:\n")
            words = first_scene.split()
            return f"S1 | {words[0]} | {words[-1]}"
        raise AssertionError("asked for something no stage asks for")


class _Author(StageVisitor):
    """Stands in for the author: reviews each stage's drafts as scripted, and
    accepts every draft the script says nothing of. It remembers the stages it
    reviewed, in the order it reviewed them, and every draft it was shown."""

    def __init__(self, reviews: dict[str, list[Review]] | None = None) -> None:
        given = reviews or {}
        self._reviews = {stage: list(stage_reviews) for stage, stage_reviews in given.items()}
        self.visited: list[str] = []
        self.shown: dict[str, list[str]] = {}

    def _reviewed(self, stage: str, draft: str) -> Review:
        if not self.visited or self.visited[-1] != stage:
            self.visited.append(stage)
        drafts = self.shown.setdefault(stage, [])
        drafts.append(draft)
        scripted = self._reviews.get(stage)
        if not scripted:
            return ACCEPT
        review = scripted.pop(0)
        return review

    def visit_plot_ideas(self, stage: PlotIdeas) -> Review:
        review = self._reviewed("plot ideas", stage.draft)
        return review

    def visit_high_level_plots(self, stage: HighLevelPlots) -> Review:
        review = self._reviewed("high-level plots", stage.draft)
        return review

    def visit_low_level_plots(self, stage: LowLevelPlots) -> Review:
        review = self._reviewed("low-level plots", stage.draft)
        return review

    def visit_meeting_points(self, stage: MeetingPoints) -> Review:
        review = self._reviewed("meeting points", stage.draft)
        return review

    def visit_concepts(self, stage: Concepts) -> Review:
        review = self._reviewed("concepts", stage.draft)
        return review

    def visit_scenes(self, stage: Scenes) -> Review:
        review = self._reviewed("scenes", stage.draft)
        return review

    def visit_choices(self, stage: Choices) -> Review:
        review = self._reviewed("choices", stage.draft)
        return review

    def visit_annotations(self, stage: Annotations) -> Review:
        review = self._reviewed("annotations", stage.draft)
        return review


class _Heard(logging.Handler):
    """Keeps every record it is handed, as the stage it was logged in and its
    message."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        stage: str = getattr(record, "stage")
        message = record.getMessage()
        self.records.append((stage, message))


def _new_story(test: unittest.TestCase) -> Path:
    """An empty story, alone in a directory of its own that is gone after the
    test."""
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    story = Path(directory.name) / "story.author"
    story.write_text("", encoding="utf-8")
    return story


def _finished(story: Path) -> list[str]:
    document = Document.load(story)
    checkpoint = get_checkpoint(document)
    assert checkpoint is not None
    finished = checkpoint.source.splitlines()
    return finished


class AFullRun(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        self.heard = _Heard()
        model = _Model()
        author = _Author(AN_IDEA)
        workflow = Workflow(self.story, model, author, self.heard)
        workflow.run()
        self.document = Document.load(self.story)

    def test_keeps_the_idea_and_its_outline_as_notes(self) -> None:
        notes = [cell.source for cell in self.document.cells if isinstance(cell, NoteCell)]

        self.assertEqual(notes, ["## Plot ideas\n\nA heist.", "## A heist.\n\nWhat A heist. is about.\n\n1. It begins."])

    def test_writes_the_events_of_the_plot(self) -> None:
        (plot,) = self.document.plots()

        events = [(event.timestamp, event.summary) for event in plot.nodes]
        self.assertEqual(events, [("1.1", "A heist. begins."), ("1.2", "A heist. ends.")])

    def test_tells_each_scene_in_a_cell_of_its_own(self) -> None:
        scene_cells = get_scene_cells(self.document)

        count = len(scene_cells)
        self.assertEqual(count, 2)

    def test_ends_a_scene_the_story_goes_on_from_in_a_choice_for_the_edge_leaving_it(self) -> None:
        (plot,) = self.document.plots()
        (edge,) = plot.edges
        first_cell, _ = get_scene_cells(self.document)

        choices_of_the_scene = get_choices(first_cell.source)

        self.assertEqual(choices_of_the_scene, {edge.edge_id: "it went on."})

    def test_annotates_every_concept_on_the_scenes(self) -> None:
        concepts_annotated = self.document.salient_concepts()

        annotated = [(concept.title, len(concept.references)) for concept in concepts_annotated]
        self.assertEqual(annotated, [("Home", 1), ("The way back", 1)])

    def test_checkpoints_every_stage_in_the_order_it_ran(self) -> None:
        finished = _finished(self.story)

        self.assertEqual(finished, STAGES_IN_ORDER)

    def test_checkpoints_in_the_story_s_last_cell_and_writes_nothing_beside_the_story(self) -> None:
        checkpoint = get_checkpoint(self.document)
        paths = self.story.parent.iterdir()
        written = sorted(path.name for path in paths)

        self.assertIs(self.document.cells[-1], checkpoint)
        self.assertEqual(written, ["story.author"])

    def test_hands_the_handler_every_record_under_the_name_of_the_stage_it_was_logged_in(self) -> None:
        first, *_ = self.heard.records

        self.assertEqual(first, ("plot ideas", "started"))
        self.assertIn(("scenes", "scene 1 of 2 accepted"), self.heard.records)


class ARevision(unittest.TestCase):
    def test_answers_the_author_s_comment(self) -> None:
        story = _new_story(self)
        commented = [Review(Verdict.REVISE, "It ends in a chase."), ACCEPT]
        model = _Model()
        author = _Author({**AN_IDEA, "high-level plots": commented, "low-level plots": [STOP]})
        heard = _Heard()
        workflow = Workflow(story, model, author, heard)

        workflow.run()

        document = Document.load(story)
        outlines = [
            cell.source for cell in document.cells if isinstance(cell, NoteCell) and cell.source.startswith("## A heist.")
        ]
        *_, accepted = author.shown["high-level plots"]
        self.assertEqual(outlines, ["## A heist.\n\nWhat A heist. is about.\n\n1. It begins.\n2. It ends in a chase."])
        self.assertEqual(accepted, outlines[0])


class StoppingInAStage(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        model = _Model()
        author = _Author({**AN_IDEA, "scenes": [STOP]})
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard)
        workflow.run()

    def test_checkpoints_only_the_stages_finished_before_it(self) -> None:
        finished = _finished(self.story)

        self.assertEqual(finished, ["plot ideas", "high-level plots", "low-level plots", "meeting points"])

    def test_resumes_at_it_when_run_again(self) -> None:
        model = _Model()
        resumed = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, resumed, heard)

        workflow.run()

        self.assertEqual(resumed.visited, ["scenes", "choices", "concepts", "annotations"])


class GoingBackToAStage(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        model = _Model()
        author = _Author(AN_IDEA)
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard)
        workflow.run()

    def test_runs_it_and_every_stage_that_depends_on_it_and_no_other(self) -> None:
        for going_back_to, run_again in {
            "low-level plots": ["low-level plots", "meeting points", "scenes", "choices", "concepts", "annotations"],
            "scenes": ["scenes", "choices", "annotations"],
            "concepts": ["concepts", "annotations"],
            "annotations": ["annotations"],
        }.items():
            with self.subTest(going_back_to=going_back_to):
                model = _Model()
                author = _Author()
                heard = _Heard()
                workflow = Workflow(self.story, model, author, heard)

                workflow.run(going_back_to)

                self.assertEqual(author.visited, run_again)

    def test_reviews_what_the_story_holds_instead_of_drafting_it_afresh(self) -> None:
        model = _Model()
        author = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard)

        workflow.run("low-level plots")

        self.assertNotIn("events", model.asked)
        self.assertNotIn("scene", model.asked)

    def test_annotates_every_concept_on_the_scenes_again(self) -> None:
        model = _Model()
        author = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard)

        workflow.run("low-level plots")

        document = Document.load(self.story)
        concepts_annotated = document.salient_concepts()
        annotated = [(concept.title, len(concept.references)) for concept in concepts_annotated]
        self.assertEqual(annotated, [("Home", 1), ("The way back", 1)])

