"""These run the whole workflow, with a model and an author standing in for the
real ones, on stories written into temporary directories."""

import logging
import random
import tempfile
import unittest
from pathlib import Path

from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices
from story_generator.stage import CAP, Confidence
from story_generator.stage_visitor import Review, StageVisitor, Verdict
from story_generator.stages import choices, concept_arcs, concepts, mesh, plot_ends, scenes
from story_generator.stages.choices import Choices
from story_generator.stages.concept_arcs import ConceptArcs, get_arcs
from story_generator.stages.concepts import Concepts
from story_generator.stages.mesh import Mesh
from story_generator.stages.plot_ends import PlotEnds
from story_generator.stages.scenes import Scenes, get_scene_cell, get_scenes
from story_generator.workflow import CONFIDENCE, STAGES, Workflow, get_checkpoint

ACCEPT = Review(Verdict.ACCEPT)
STOP = Review(Verdict.STOP)
# The author says what the story is about, and accepts the list.
ABOUT = {"concepts": [Review(Verdict.REVISE, "Home, The way back"), ACCEPT]}


class _Drawing(random.Random):
    """Draws the same number every time."""

    def __init__(self, drawn: float) -> None:
        super().__init__()
        self._drawn = drawn

    def random(self) -> float:
        return self._drawn


# Draws 0, which every level of confidence selects: the author reviews every draft.
EVERY_DRAFT = _Drawing(0.0)


def _between(text: str, start: str, end: str = "\n\n") -> str:
    """The text after the first `start`, up to the `end` that follows it."""
    _, _, after = text.partition(start)
    found, _, _ = after.partition(end)
    return found


class _Model:
    """Stands in for the model. The concepts are the titles the author's latest
    comment lists, each described by its title; every plot starts and ends in its
    concept's house, at 1 and 9, and is filled in with a walk through the square
    at 5, where every plot meets; every concept shows at every event of its plot
    but the last, at 9; a version of a scene is its event, said back; a
    merge puts the next version after the scene merged so far, and leaves a draft
    under review as it is; and every choice is "Then, it went on.". It remembers
    what it was asked for, every version it was asked for, as its event and its
    concept, and every scene merged so far it was given."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.versions: list[tuple[str, str]] = []
        self.merged_so_far: list[str] = []

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        if system == concepts.LIST_INSTRUCTIONS:
            self.asked.append("concepts")
            comments = _between(user, "The author's comments, oldest first:\n", "\n\n\n")
            lines = comments.splitlines()
            latest = lines[-1]
            listed = latest.removeprefix("- ")
            titles = listed.split(", ")
            return "\n".join(titles)
        if system == concepts.DESCRIPTION_INSTRUCTIONS:
            self.asked.append("description")
            title = _between(user, "The concept to describe: ", "\n")
            if "The author's comments" not in user:
                return f"What {title} means."
            comments = _between(user, "The author's comments, oldest first:\n", "\n\n\n")
            lines = comments.splitlines()
            latest = lines[-1]
            comment = latest.removeprefix("- ")
            return f"What {title} means, {comment}"
        if system == plot_ends.INSTRUCTIONS:
            self.asked.append("ends")
            title = _between(user, "The concept whose plot to begin, ", ":\n")
            return f"1 | earth, {title}'s house | {title} begins.\n9 | earth, {title}'s house | {title} ends."
        if system == mesh.INSTRUCTIONS:
            self.asked.append("events")
            title = _between(user, "The plot to fill in, ", ", which illustrates")
            events = _between(user, f"which illustrates {title}:\n")
            start, goal = events.splitlines()
            return f"{start}\n5 | earth, the square | {title} walks through the square.\n{goal}"
        if system == concept_arcs.INSTRUCTIONS:
            self.asked.append("arcs")
            to_fill = _between(user, "The plot's events, each followed by its concepts:\n")
            filled = []
            event = ""
            for line in to_fill.splitlines():
                if not line.startswith(" "):
                    event = line
                    filled.append(line)
                    continue
                title, _, _ = line.partition(":")
                concept = title.strip()
                how = "—" if event.startswith("9 ") else f"{concept} shows here."
                filled.append(f"{title}: {how}")
            return "\n".join(filled)
        if system == scenes.VERSION_INSTRUCTIONS:
            self.asked.append("version")
            event = _between(user, "The event: ")
            title = _between(user, "The concept, ", ":\n")
            self.versions.append((event, title))
            return event
        if system == scenes.MERGE_INSTRUCTIONS:
            self.asked.append("merge")
            if "Your draft:\n" in user:
                draft = _between(user, "Your draft:\n", "\n\nThe author's comments")
                return draft
            so_far = _between(user, "The scene as merged so far:\n")
            if so_far:
                self.merged_so_far.append(so_far)
            next_version = _between(user, "The next version:\n")
            merged = f"{so_far} {next_version}"
            return merged.strip()
        if system == choices.OPENING_INSTRUCTIONS:
            self.asked.append("opening")
            return "Then,"
        if system == choices.ENDING_INSTRUCTIONS:
            self.asked.append("ending")
            return "it went on."
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

    def visit_concepts(self, stage: Concepts) -> Review:
        review = self._reviewed("concepts", stage.draft)
        return review

    def visit_plot_ends(self, stage: PlotEnds) -> Review:
        review = self._reviewed("plot ends", stage.draft)
        return review

    def visit_mesh(self, stage: Mesh) -> Review:
        review = self._reviewed("mesh", stage.draft)
        return review

    def visit_concept_arcs(self, stage: ConceptArcs) -> Review:
        review = self._reviewed("concept arcs", stage.draft)
        return review

    def visit_scenes(self, stage: Scenes) -> Review:
        review = self._reviewed("scenes", stage.draft)
        return review

    def visit_choices(self, stage: Choices) -> Review:
        review = self._reviewed("choices", stage.draft)
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


class _LosingMarkers(_Model):
    """Stands in for the model as `_Model` does, but loses the markers of its first
    merge."""

    def __init__(self) -> None:
        super().__init__()
        self.lost = False

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        written = super().complete(system, user, max_new_tokens)
        if system != scenes.MERGE_INSTRUCTIONS or self.lost:
            return written
        self.lost = True
        unmarked = scenes.MARKER.sub("", written)
        return unmarked


class _Died(Exception):
    """The run died, as it does when the model stops answering and the run is
    killed."""


class _DyingAtTheSecondDescription(_Model):
    """Stands in for the model as `_Model` does, until it is asked to describe a
    second concept: then the run dies."""

    def __init__(self) -> None:
        super().__init__()
        self.descriptions = 0

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        if system == concepts.DESCRIPTION_INSTRUCTIONS:
            self.descriptions += 1
            if self.descriptions == 2:
                raise _Died
        written = super().complete(system, user, max_new_tokens)
        return written


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
    lines = checkpoint.source.splitlines()
    finished = [line for line in lines if not line.startswith(CONFIDENCE)]
    return finished


def _passages(story: Path) -> dict[str, list[str]]:
    """Every concept's passages, by its title, as the words they point at."""
    document = Document.load(story)
    story_words = StoryWordsIterator(document)
    passages = {}
    for concept in document.salient_concepts():
        texts = [story_words.text(reference.story_word_range) for reference in concept.references]
        passages[concept.title] = texts
    return passages


class AFullRun(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        self.model = _Model()
        self.author = _Author(ABOUT)
        self.heard = _Heard()
        workflow = Workflow(self.story, self.model, self.author, self.heard, EVERY_DRAFT)
        workflow.run()
        self.document = Document.load(self.story)

    def test_keeps_the_concepts_the_author_named_each_described(self) -> None:
        concepts_kept = self.document.salient_concepts()

        described = [(concept.title, concept.source) for concept in concepts_kept]
        self.assertEqual(described, [("Home", "What Home means."), ("The way back", "What The way back means.")])

    def test_gives_every_concept_a_plot_from_its_start_to_its_goal(self) -> None:
        home, way_back = self.document.plots()

        events = [(event.timestamp, event.location, event.summary) for event in home.nodes]
        self.assertEqual((way_back.title, way_back.overview), ("The way back", "Illustrates: The way back"))
        self.assertEqual(
            events,
            [
                ("1", "earth, Home's house", "Home begins."),
                ("5", "earth, the square", "Home walks through the square."),
                ("9", "earth, Home's house", "Home ends."),
            ],
        )

    def test_plans_how_every_concept_shows_at_every_event_of_its_plot(self) -> None:
        home, _ = self.document.plots()

        arcs = get_arcs(self.document, home)

        self.assertEqual(arcs, [{"Home": "Home shows here."}, {"Home": "Home shows here."}, {}])

    def test_writes_no_version_for_a_concept_where_it_does_not_show(self) -> None:
        versions_of_home = [title for event, title in self.model.versions if event.startswith("Home")]

        self.assertEqual(versions_of_home, ["Home", "Home", ""])

    def test_tells_each_scene_in_a_cell_of_its_own(self) -> None:
        scenes_now = get_scenes(self.document)

        told = [get_scene_cell(self.document, scene) for scene in scenes_now]
        cell_ids = {cell.unique_id for cell in told if cell is not None}
        self.assertEqual(len(cell_ids), 5)

    def test_writes_a_version_for_every_concept_of_a_scene_and_merges_them_one_at_a_time(self) -> None:
        scene_drafts = self.author.shown["scenes"]

        # Five scenes, one of them where both plots meet: a version and a merge
        # for each event, and two of each where the plots meet.
        reviewed = len(scene_drafts)
        self.assertEqual(reviewed, 12)
        self.assertEqual(self.model.merged_so_far, ["⟦Home⟧Home walks through the square.⟦/Home⟧"])

    def test_keeps_the_passages_the_writer_marked_after_the_choices_are_written(self) -> None:
        passages = _passages(self.story)

        self.assertEqual(
            passages,
            {
                "Home": ["Home begins.", "Home walks through the square."],
                "The way back": ["The way back begins.", "The way back walks through the square."],
            },
        )

    def test_ends_a_scene_the_story_goes_on_from_in_a_choice_for_every_edge_leaving_it(self) -> None:
        scenes_now = get_scenes(self.document)
        in_the_square = scenes_now[2]
        cell = get_scene_cell(self.document, in_the_square)
        assert cell is not None

        choices_of_the_scene = get_choices(cell.source)

        endings = list(choices_of_the_scene.values())
        self.assertEqual(endings, ["it went on.", "it went on."])

    def test_checkpoints_every_stage_in_the_order_it_ran(self) -> None:
        finished = _finished(self.story)

        self.assertEqual(finished, STAGES)

    def test_checkpoints_in_the_story_s_last_cell_and_writes_nothing_beside_the_story(self) -> None:
        checkpoint = get_checkpoint(self.document)
        paths = self.story.parent.iterdir()
        written = sorted(path.name for path in paths)

        self.assertIs(self.document.cells[-1], checkpoint)
        self.assertEqual(written, ["story.author"])

    def test_hands_the_handler_every_record_under_the_name_of_the_stage_it_was_logged_in(self) -> None:
        first, *_ = self.heard.records

        self.assertEqual(first, ("concepts", "started"))
        self.assertIn(("scenes", "scene 3 of 5 accepted"), self.heard.records)


class ARevision(unittest.TestCase):
    def test_answers_the_author_s_comment(self) -> None:
        story = _new_story(self)
        commented = [Review(Verdict.REVISE, "told from far away."), ACCEPT]
        model = _Model()
        author = _Author({"concepts": [*ABOUT["concepts"], *commented], "plot ends": [STOP]})
        heard = _Heard()
        workflow = Workflow(story, model, author, heard, EVERY_DRAFT)

        workflow.run()

        document = Document.load(story)
        home, _ = document.salient_concepts()
        self.assertEqual(home.source, "What Home means, told from far away.")


class StoppingInAStage(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        model = _Model()
        author = _Author({**ABOUT, "scenes": [STOP]})
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)
        workflow.run()

    def test_checkpoints_only_the_stages_finished_before_it(self) -> None:
        finished = _finished(self.story)

        self.assertEqual(finished, ["concepts", "plot ends", "mesh", "concept arcs"])

    def test_resumes_at_it_when_run_again(self) -> None:
        model = _Model()
        resumed = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, resumed, heard, EVERY_DRAFT)

        workflow.run()

        self.assertEqual(resumed.visited, ["scenes", "choices"])

    def test_writes_a_version_of_an_event_for_every_concept_its_plot_illustrates(self) -> None:
        document = Document.load(self.story)
        home, _ = document.plots()
        illustrating_both = home.with_overview("What a home is.\nIllustrates: Home, The way back")
        cells = [illustrating_both if cell.unique_id == home.unique_id else cell for cell in document.cells]
        both = Document.from_cells(cells, document.path)
        self.story.write_text(both.text, encoding="utf-8")
        model = _Model()
        author = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)

        workflow.run("concept arcs")

        first, second, *_ = model.versions
        passages = _passages(self.story)
        self.assertEqual([first, second], [("Home begins.", "Home"), ("Home begins.", "The way back")])
        self.assertIn("Home begins.", passages["The way back"])


class GoingBackToAStage(unittest.TestCase):
    def setUp(self) -> None:
        self.story = _new_story(self)
        model = _Model()
        author = _Author(ABOUT)
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)
        workflow.run()

    def test_runs_it_and_every_stage_after_it(self) -> None:
        for going_back_to in STAGES:
            with self.subTest(going_back_to=going_back_to):
                model = _Model()
                author = _Author()
                heard = _Heard()
                workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)

                workflow.run(going_back_to)

                at = STAGES.index(going_back_to)
                self.assertEqual(author.visited, STAGES[at:])

    def test_reviews_what_the_story_holds_instead_of_drafting_it_afresh(self) -> None:
        model = _Model()
        author = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)

        workflow.run("concepts")

        self.assertEqual(model.asked, [])

    def test_keeps_the_passages_of_the_scenes_it_reviews_again(self) -> None:
        passages_before = _passages(self.story)
        model = _Model()
        author = _Author()
        heard = _Heard()
        workflow = Workflow(self.story, model, author, heard, EVERY_DRAFT)

        workflow.run("scenes")

        passages_after = _passages(self.story)
        self.assertEqual(passages_after, passages_before)


class MarkingPassages(unittest.TestCase):
    def test_sends_back_a_merge_that_loses_its_markers(self) -> None:
        story = _new_story(self)
        model = _LosingMarkers()
        author = _Author(ABOUT)
        heard = _Heard()
        workflow = Workflow(story, model, author, heard, EVERY_DRAFT)

        workflow.run()

        sent_back = ("scenes", "the merge's markers are wrong, so it is sent back: no pair of ⟦Home⟧")
        passages = _passages(story)
        self.assertIn(sent_back, heard.records)
        self.assertEqual(passages["Home"], ["Home begins.", "Home walks through the square."])

    def test_reads_the_span_of_every_pair_of_markers_even_where_pairs_overlap(self) -> None:
        text, spans, problems = scenes.read_marked("⟦A⟧one ⟦B⟧two⟦/A⟧ three⟦/B⟧")

        self.assertEqual(text, "one two three")
        self.assertEqual(spans, [scenes.Span("A", 0, 7), scenes.Span("B", 4, 13)])
        self.assertEqual(problems, [])

    def test_writes_the_markers_back_where_the_spans_are(self) -> None:
        spans = [scenes.Span("A", 0, 7), scenes.Span("B", 4, 13)]

        marked = scenes.written_marked("one two three", spans)

        self.assertEqual(marked, "⟦A⟧one ⟦B⟧two⟦/A⟧ three⟦/B⟧")


class TheConfidence(unittest.TestCase):
    def test_rises_a_fifth_of_the_way_to_certainty_with_every_draft_accepted_as_drafted(self) -> None:
        confidence = Confidence({}, EVERY_DRAFT)

        confidence.accepted("scene versions")
        once = confidence.level("scene versions")
        confidence.accepted("scene versions")
        twice = confidence.level("scene versions")

        self.assertAlmostEqual(once, 0.2)
        self.assertAlmostEqual(twice, 0.36)

    def test_halves_with_every_draft_revised(self) -> None:
        confidence = Confidence({"scene versions": 0.5}, EVERY_DRAFT)

        confidence.revised("scene versions")

        level = confidence.level("scene versions")
        self.assertAlmostEqual(level, 0.25)

    def test_never_rises_above_its_cap(self) -> None:
        confidence = Confidence({}, EVERY_DRAFT)

        for _ in range(50):
            confidence.accepted("scene versions")

        level = confidence.level("scene versions")
        self.assertEqual(level, CAP)

    def test_selects_a_draft_for_review_the_less_likely_the_more_confident_it_is(self) -> None:
        drawn_high = _Drawing(0.6)
        drawn_low = _Drawing(0.4)
        unsure = Confidence({}, drawn_high)
        sure = Confidence({"scene versions": 0.5}, drawn_high)
        sure_but_drawn_low = Confidence({"scene versions": 0.5}, drawn_low)

        selected = [
            unsure.selects("scene versions"),
            sure.selects("scene versions"),
            sure_but_drawn_low.selects("scene versions"),
        ]

        self.assertEqual(selected, [True, False, True])


class SelectiveReview(unittest.TestCase):
    def test_accepts_unseen_a_draft_the_confidence_does_not_select_and_logs_it(self) -> None:
        story = _new_story(self)
        model = _Model()
        author = _Author(ABOUT)
        heard = _Heard()
        # Drawn high, a draft is reviewed only while its kind has no confidence:
        # the first of every kind.
        workflow = Workflow(story, model, author, heard, _Drawing(0.95))

        workflow.run()

        reviewed_descriptions = author.shown["concepts"][2:]
        unseen = ("concepts", "a draft of concept descriptions was accepted unreviewed, at confidence 0.20")
        concepts_kept = Document.load(story).salient_concepts()
        described = [concept.source for concept in concepts_kept]
        self.assertEqual(reviewed_descriptions, ["What Home means."])
        self.assertIn(unseen, heard.records)
        self.assertEqual(described, ["What Home means.", "What The way back means."])

    def test_always_shows_the_list_of_concepts(self) -> None:
        story = _new_story(self)
        model = _Model()
        author = _Author({**ABOUT, "plot ends": [STOP]})
        heard = _Heard()
        confident = Workflow(story, model, author, heard, _Drawing(0.99))

        confident.run()

        lists_shown = author.shown["concepts"][:2]
        self.assertEqual(lists_shown, ["", "Home\nThe way back"])

    def test_keeps_the_confidence_when_the_author_stops_and_resumes_with_it(self) -> None:
        story = _new_story(self)
        model = _Model()
        author = _Author({**ABOUT, "plot ends": [STOP]})
        heard = _Heard()
        workflow = Workflow(story, model, author, heard, EVERY_DRAFT)

        workflow.run()

        resumed = Workflow(story, model, author, heard, EVERY_DRAFT)
        confidence = resumed.confidence()
        level = confidence.level("concept descriptions")
        self.assertAlmostEqual(level, 0.36)

    def test_keeps_the_confidence_of_every_draft_written_when_the_run_dies_in_a_stage(self) -> None:
        story = _new_story(self)
        model = _DyingAtTheSecondDescription()
        author = _Author(ABOUT)
        heard = _Heard()
        workflow = Workflow(story, model, author, heard, EVERY_DRAFT)

        with self.assertRaises(_Died):
            workflow.run()

        resumed = Workflow(story, model, author, heard, EVERY_DRAFT)
        confidence = resumed.confidence()
        level = confidence.level("concept descriptions")
        self.assertAlmostEqual(level, 0.2)
