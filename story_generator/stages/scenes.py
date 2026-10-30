"""A scene for every group of events that meet, built from versions dedicated to
its concepts, and kept in a markdown cell that every event of the scene points
at, the whole of it.

Events meet when they happen at the same moment, in places one of which holds
the other. For every event of a scene, and every concept of its plot that shows
at the event, as the plot's concept arcs say, the model writes a version of the
scene dedicated to that concept: the event, told wholly through the concept as
its arc says it shows there, so that all of the version shows it. The
versions are then merged into the scene, one after another: each comes into the
merge between the markers of its concept, ⟦<concept>⟧ and ⟦/<concept>⟧, and the
merge blends it into the scene so far, keeping every pair of markers, and adds
around them what a scene needs. Where a sentence comes to show two concepts,
their pairs overlap. What stands between a concept's markers in the finished
scene are the concept's passages: written for the concept, never found in the
scene afterwards. The author reviews every version and every merge.

A scene's words are numbered with the story's, so writing a cell moves the words
of every cell after it. Every event is then pointed again at the whole of the
cell that tells it, and every concept's passages at the words that stand where
they stood: in which cell, and between which of its characters.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.cell import Cell
from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell, SalientConceptReference
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWord, StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import GAP, get_choices, get_place, get_scene_text, get_tag, tags_meet, written_scene
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Confidence, Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.concept_arcs import get_arcs
from story_generator.stages.concepts import written_concepts
from story_generator.stages.plot_ends import get_illustrated, written_world_events

VERSION_INSTRUCTIONS = """You write one version of a scene of an interactive story, dedicated to one salient concept: the scene's event, told wholly through that concept, so that every sentence of the version shows the concept's idea, though it never names it. A later pass merges this version with the versions dedicated to the scene's other concepts, and adds what a scene needs beyond them.

You are the story's narrator and its only witness: you never take part in what happens and never mention yourself. Write in the third person and the past tense: the people, what they do and say, and how that shows the concept. Add no named characters and no events of your own.

You are given the story's concepts and plots, so that the version agrees with them; show nothing from the plots beyond the event. You are given where the scene takes place, the event, the concept, and how the concept shows at this event. Write the version as that says: what of the event does not show the concept stays out of it, for the merge adds it.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change. The draft stands between the markers of its concept, ⟦<the concept>⟧ and ⟦/<the concept>⟧; write the version without them.

Write one or two paragraphs of prose and nothing else."""

MERGE_INSTRUCTIONS = """You write one scene of an interactive story, the way a text adventure such as Zork shows a location: whoever reads it may have come to it from anywhere in the story, so it stands on its own. It says nothing of what happened before it, and nothing of what may happen after it. You are the story's narrator and its only witness: you never take part in what happens and never mention yourself. Write in the third person and the past tense.

The scene is built from versions, each dedicated to one salient concept and marked with it: the version's text stands between ⟦<the concept>⟧ and ⟦/<the concept>⟧. You are given the story's concepts and plots, where the scene takes place and what happens there, the scene as merged so far, when there is one, and the next version. Merge them into one scene: blend their texts so that they read as one, and add around them what a scene needs: the place, pacing, dialogue, description.

Keep every pair of markers, and keep between each pair the text that shows its concept, rewritten as the blending needs. Text you add that shows no concept goes outside every pair. Where a sentence comes to show two concepts, their pairs may overlap.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, keep every pair of markers, and change nothing the comments do not ask you to change.

Write the scene with its markers, two to five paragraphs of prose, and nothing else."""

# Room for a version of a paragraph or two.
MAX_VERSION_TOKENS = 1500

# Room for a scene of a few paragraphs, with its markers.
MAX_MERGE_TOKENS = 3000

# How many times a merge whose markers are wrong is sent back.
MERGE_ATTEMPTS = 3

# A concept's marker: opening, or, with the slash, closing the concept's text.
MARKER = re.compile(r"⟦(/?)([^⟦⟧]+)⟧")


@dataclass(frozen=True)
class Span:
    """Where a concept's passage stands in a scene."""

    concept: str
    start: int
    end: int


@dataclass(frozen=True)
class Anchor:
    """Where a passage of a salient concept stands: in which cell, between which of
    its characters. It stays there however the story's other cells change, and
    gives the passage its words again once they have moved."""

    reference_id: str
    cell_id: str
    start: int
    end: int


def get_scenes(document: Document) -> list[list[PlotNode]]:
    """Every event with a moment and a place, grouped with every event it meets,
    directly or through another, in the order of the clock, and within a scene in
    the order the plots give them. An event without a moment or a place is in no
    scene."""
    scenes: list[list[PlotNode]] = []
    for plot in document.plots():
        for event in plot.nodes:
            tag = get_tag(event)
            if tag is None:
                continue
            met = [scene for scene in scenes if _meets(scene, tag)]
            joined = [other for scene in met for other in scene]
            scenes = [scene for scene in scenes if scene not in met]
            scenes.append([*joined, event])
    scenes.sort(key=_moment_of)
    return scenes


def get_cell_of_event(document: Document) -> dict[str, str]:
    """The id of the cell each told event points at: the cell of its first word."""
    cell_of_word = {word.number: word.cell_id for word in StoryWordsIterator(document)}
    cell_of_event = {
        event.node_id: cell_of_word[event.story_word_range.first_word]
        for plot in document.plots()
        for event in plot.nodes
        if event.story_word_range is not None and event.story_word_range.first_word in cell_of_word
    }
    return cell_of_event


def get_scene_cell(document: Document, scene: list[PlotNode]) -> Cell | None:
    """The cell that tells the scene: the one every event of the scene points at,
    and no other event does. None when the scene is not told yet."""
    cell_of_event = get_cell_of_event(document)
    scene_ids = {event.node_id for event in scene}
    cell_ids = {cell_of_event.get(event_id) for event_id in scene_ids}
    if len(cell_ids) != 1 or None in cell_ids:
        return None
    (cell_id,) = cell_ids
    told_there = {event_id for event_id, told_in in cell_of_event.items() if told_in == cell_id}
    if told_there != scene_ids:
        return None
    cell = document.cell_with_id(cell_id)
    return cell


def get_scene_prose(source: str) -> str:
    """What a scene's cell tells, without the sentence it leaves unfinished and
    the choices that finish it."""
    told = get_scene_text(source)
    if not told.endswith(GAP):
        return told
    prose, _, _ = told.rpartition("\n\n")
    return prose


def get_scene_opening(source: str) -> str | None:
    """The opening of the sentence a scene's cell leaves unfinished; None for a
    scene with no choices."""
    told = get_scene_text(source)
    if not told.endswith(GAP):
        return None
    _, _, unfinished = told.rpartition("\n\n")
    without_the_gap = unfinished.removesuffix(GAP)
    opening = without_the_gap.strip()
    return opening


def get_anchors(document: Document) -> dict[str, list[Anchor]]:
    """Where every salient concept's passages stand, by the concept's id."""
    story_words = StoryWordsIterator(document)
    anchors_of_concept: dict[str, list[Anchor]] = {}
    for concept in document.salient_concepts():
        anchors = []
        for reference in concept.references:
            spans = story_words.spans(reference.story_word_range)
            if not spans:
                continue
            first_span, *_ = spans
            anchor = Anchor(
                reference.reference_id,
                first_span.cell_id,
                first_span.start_character_offset_in_cell,
                first_span.end_character_offset_in_cell,
            )
            anchors.append(anchor)
        anchors_of_concept[concept.unique_id] = anchors
    return anchors_of_concept


def with_words_pointed(
    document: Document, cell_of_event: dict[str, str], anchors_of_concept: dict[str, list[Anchor]]
) -> Document:
    """The document with every event in `cell_of_event` pointed at the whole of the
    cell that tells it, wherever that cell's words now stand, every other event
    untold, and every salient concept's passages pointed at the words that stand
    where its anchors are; a passage whose words are gone is gone."""
    words_of_cell: dict[str, list[StoryWord]] = {}
    for word in StoryWordsIterator(document):
        cell_words = words_of_cell.setdefault(word.cell_id, [])
        cell_words.append(word)
    cells: list[Cell] = []
    for cell in document.cells:
        if isinstance(cell, SalientConceptCell):
            anchors = anchors_of_concept.get(cell.unique_id, [])
            references = []
            for anchor in anchors:
                anchored_words = words_of_cell.get(anchor.cell_id, [])
                numbers = [
                    word.number
                    for word in anchored_words
                    if word.end_character_offset_in_cell > anchor.start and word.start_character_offset_in_cell < anchor.end
                ]
                if not numbers:
                    continue
                passage_words = StoryWordRange(numbers[0], numbers[-1])
                reference = SalientConceptReference(anchor.reference_id, passage_words)
                references.append(reference)
            annotated = replace(cell, references=references)
            cells.append(annotated)
            continue
        if not isinstance(cell, PlotCell):
            cells.append(cell)
            continue
        events = []
        for event in cell.nodes:
            cell_id = cell_of_event.get(event.node_id)
            told_words = words_of_cell.get(cell_id, []) if cell_id is not None else []
            words = StoryWordRange(told_words[0].number, told_words[-1].number) if told_words else None
            told = replace(event, story_word_range=words)
            events.append(told)
        plot_told = replace(cell, nodes=events)
        cells.append(plot_told)
    story = Document.from_cells(cells, document.path)
    return story


def read_marked(marked: str) -> tuple[str, list[Span], list[str]]:
    """A marked scene's text without its markers, the span of every pair of
    markers in that text, and what is wrong with the markers: one that closes no
    pair, or one never closed. Pairs may overlap."""
    parts: list[str] = []
    length = 0
    at = 0
    opened_at: dict[str, list[int]] = {}
    spans: list[Span] = []
    problems: list[str] = []
    for marker in MARKER.finditer(marked):
        marker_start = marker.start()
        before = marked[at:marker_start]
        parts.append(before)
        length += len(before)
        at = marker.end()
        closing = marker.group(1)
        written_title = marker.group(2)
        title = written_title.strip()
        if not closing:
            starts = opened_at.setdefault(title, [])
            starts.append(length)
            continue
        starts = opened_at.get(title, [])
        if not starts:
            problems.append(f"⟦/{title}⟧ closes no ⟦{title}⟧")
            continue
        start = starts.pop()
        span = Span(title, start, length)
        spans.append(span)
    rest = marked[at:]
    parts.append(rest)
    for title, starts in opened_at.items():
        unclosed = [f"⟦{title}⟧ is never closed" for _ in starts]
        problems.extend(unclosed)
    text = "".join(parts)
    # The text is kept without the blank around it, and every span moves with it.
    unindented = text.lstrip()
    shift = len(text) - len(unindented)
    stripped = unindented.rstrip()
    end_of_text = len(stripped)
    kept = [
        Span(span.concept, max(span.start - shift, 0), min(span.end - shift, end_of_text))
        for span in spans
    ]
    moved = [span for span in kept if span.start < span.end]
    return (stripped, moved, problems)


def written_marked(text: str, spans: Sequence[Span]) -> str:
    """The text with every span between the markers of its concept."""
    # Where two markers stand at one place, a pair that closes there closes
    # before one opens.
    markers = []
    for span in spans:
        markers.append((span.start, 1, f"⟦{span.concept}⟧"))
        markers.append((span.end, 0, f"⟦/{span.concept}⟧"))
    markers.sort(key=lambda marker: (marker[0], marker[1]))
    parts = []
    at = 0
    for place, _, written in markers:
        parts.append(text[at:place])
        parts.append(written)
        at = place
    rest = text[at:]
    parts.append(rest)
    marked = "".join(parts)
    return marked


def get_marking_problems(marked: str, expected: Sequence[str]) -> list[str]:
    """What is wrong with a marked scene's markers: a pair that closes nothing or
    is never closed, a concept expected with no pair, and a pair of a concept
    that is not expected."""
    _, spans, problems = read_marked(marked)
    marked_titles = {span.concept for span in spans}
    missing = [f"no pair of ⟦{title}⟧" for title in expected if title not in marked_titles]
    unexpected = [f"⟦{title}⟧ is no concept of the scene" for title in sorted(marked_titles) if title not in expected]
    all_problems = [*problems, *missing, *unexpected]
    return all_problems


class Scenes(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the draft: when and where the scene
        # happens, what happens there, each event with the plot it belongs to and
        # the concepts that show at it, and what the draft is: which version, or
        # which merge.
        self.moment = ""
        self.place = ""
        self.towards: list[tuple[str, str, str]] = []
        self.under_review = ""
        # The version under review: its concept, its event and the plot the event
        # belongs to, and how the concept shows there; none while a merge is.
        self.version_concept = ""
        self.version_event = ""
        self.version_plot = ""
        self.version_shows = ""
        # The merge being written: the scene merged so far, the next version, and
        # the concepts whose pairs of markers it must keep.
        self._so_far = ""
        self._next = ""
        self._expected: list[str] = []

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        confidence: Confidence = params["confidence"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        scenes_at_the_start = get_scenes(document)
        count = len(scenes_at_the_start)
        for index in range(count):
            # The scenes are taken from the story as it now stands, so that their
            # events point at the words they now have.
            scenes = get_scenes(document)
            scene = scenes[index]
            self.moment = scene[0].timestamp
            self.place = get_place(scene)
            self.progress = (index, count)
            concepts = document.salient_concepts()
            # How every concept shows at every event, as its plot's arcs say; a plot
            # with no arcs has every concept show at every event.
            shows_of_event: dict[str, dict[str, str]] = {}
            plot_of_event: dict[str, str] = {}
            for plot in document.plots():
                illustrated = get_illustrated(plot)
                arcs = get_arcs(document, plot)
                every_concept = {title: "" for title in illustrated}
                for at, event in enumerate(plot.nodes):
                    shows_of_event[event.node_id] = arcs[at] if arcs is not None else every_concept
                    plot_of_event[event.node_id] = plot.title
            self.towards = []
            for event in scene:
                shows = shows_of_event[event.node_id]
                written_shows = ", ".join(shows) or "no concept shows here"
                self.towards.append((plot_of_event[event.node_id], event.summary, written_shows))
            # Every event's version for every concept that shows at it; one, with no
            # concept, for an event where none shows.
            versions_to_write = [
                (plot_of_event[event.node_id], event.summary, title, how)
                for event in scene
                for title, how in shows_of_event[event.node_id].items() or [("", "")]
            ]
            self._expected = [title for _, _, title, _ in versions_to_write if title]
            held = get_scene_cell(document, scene)
            anchors_of_concept = get_anchors(document)

            def revised_version(comments: list[str]) -> str:
                version = self._version(document, comments)
                return version

            def revised_merge(comments: list[str]) -> str:
                merge = self._merged(document, comments)
                return merge

            if held is not None:
                # A scene told before is reviewed whole, as the story holds it.
                self.under_review = "The scene, as the story holds it"
                self.version_concept = ""
                self.version_event = ""
                self.version_plot = ""
                self.version_shows = ""
                self._so_far = ""
                self._next = ""
                prose = get_scene_prose(held.source)
                held_spans = _get_spans(concepts, anchors_of_concept, held.unique_id)
                self.draft = written_marked(prose, held_spans)
                merged = reviewed(self, renderer, revised_merge, confidence, "scene merges")
            else:
                versions = []
                count_versions = len(versions_to_write)
                for number, (plot_title, summary, title, how) in enumerate(versions_to_write, start=1):
                    self.version_plot = plot_title
                    self.version_event = summary
                    self.version_concept = title
                    self.version_shows = how
                    self.under_review = f"Version {number} of {count_versions}"
                    self.draft = self._version(document, [])
                    version = reviewed(self, renderer, revised_version, confidence, "scene versions")
                    versions.append(version)
                self.version_concept = ""
                self.version_event = ""
                self.version_plot = ""
                self.version_shows = ""
                merged = ""
                for number, version in enumerate(versions, start=1):
                    self.under_review = f"Merge {number} of {count_versions}"
                    self._so_far = merged
                    self._next = version
                    self.draft = self._merged(document, [])
                    merged = reviewed(self, renderer, revised_merge, confidence, "scene merges")
            scene_text, spans, _ = read_marked(merged)
            cell_of_event = get_cell_of_event(document)
            if held is not None:
                # The scene keeps the choices it ended with; the choices stage
                # reviews them again.
                held_opening = get_scene_opening(held.source)
                held_choices = get_choices(held.source)
                source = written_scene(scene_text, held_opening, held_choices) if held_opening is not None else scene_text
                scene_cell = held.with_source(source)
                cells = [scene_cell if cell.unique_id == held.unique_id else cell for cell in document.cells]
            else:
                scene_cell = MarkdownCell(source=scene_text)
                cells = [*document.cells, scene_cell]
            for event in scene:
                cell_of_event[event.node_id] = scene_cell.unique_id
            # The scene's passages are the ones marked in it now; every other
            # passage stays where it stands.
            anchors_now = {
                concept_id: [anchor for anchor in anchors if anchor.cell_id != scene_cell.unique_id]
                for concept_id, anchors in anchors_of_concept.items()
            }
            id_of_concept = {concept.title: concept.unique_id for concept in concepts}
            for span in spans:
                concept_id = id_of_concept.get(span.concept)
                if concept_id is None:
                    logger.warning("%s is no concept of the story; its passage is left out", span.concept)
                    continue
                identifier = uuid4()
                reference_id = str(identifier)
                anchor = Anchor(reference_id, scene_cell.unique_id, span.start, span.end)
                concept_anchors = anchors_now.setdefault(concept_id, [])
                concept_anchors.append(anchor)
            written = Document.from_cells(cells, document.path)
            document = with_words_pointed(written, cell_of_event, anchors_now)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("scene %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_scenes(self)
        return review

    def _context(self, document: Document) -> str:
        """What every request about the scene begins with: the story's concepts and
        plots, and where the scene takes place."""
        concepts = document.salient_concepts()
        written_story_concepts = written_concepts(concepts)
        plots = written_world_events(document, "")
        context = (
            f"The story's concepts:\n{written_story_concepts}\n\n"
            f"The story's plots:\n{plots}\n\n"
            f"Where the scene takes place: {self.place}"
        )
        return context

    def _version(self, document: Document, comments: list[str]) -> str:
        """The version of the scene dedicated to its concept, drafted afresh, or,
        given the author's comments, the draft under review revised to answer
        them; between the markers of its concept, all of it, as it comes into
        the merge."""
        context = self._context(document)
        concepts = document.salient_concepts()
        description = next((concept.source for concept in concepts if concept.title == self.version_concept), "")
        written_concept = (
            f"The concept, {self.version_concept}:\n{description}"
            if self.version_concept
            else "The concept: none; tell the event plainly."
        )
        if self.version_shows:
            written_concept = f"{written_concept}\n\nHow it shows at this event: {self.version_shows}"
        request = f"{context}\n\nThe plot the event belongs to: {self.version_plot}\n\nThe event: {self.version_event}\n\n{written_concept}"
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(VERSION_INSTRUCTIONS, request, MAX_VERSION_TOKENS)
        # Markers the model kept from its draft are its concept's, put back below.
        text, _, _ = read_marked(written)
        if not self.version_concept:
            return text
        version = f"⟦{self.version_concept}⟧{text}⟦/{self.version_concept}⟧"
        return version

    def _merged(self, document: Document, comments: list[str]) -> str:
        """The next version merged into the scene so far, or, given the author's
        comments, the draft under review revised to answer them; sent back while
        its markers are wrong, as many times as a merge is."""
        logger = logging.getLogger(__name__)
        context = self._context(document)
        happening = "\n".join(f"- {plot}: {summary} ({concepts})" for plot, summary, concepts in self.towards)
        request = f"{context}\n\nWhat happens there:\n{happening}"
        if self._so_far:
            request = f"{request}\n\nThe scene as merged so far:\n{self._so_far}"
        if self._next:
            request = f"{request}\n\nThe next version:\n{self._next}"
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        expected_now = [title for title in self._expected if f"⟦{title}⟧" in f"{self._so_far}{self._next}{self.draft}"]
        marked = ""
        for _ in range(MERGE_ATTEMPTS):
            written = self._model.complete(MERGE_INSTRUCTIONS, request, MAX_MERGE_TOKENS)
            marked = written.strip()
            problems = get_marking_problems(marked, expected_now)
            if not problems:
                return marked
            listed = "; ".join(problems)
            logger.warning("the merge's markers are wrong, so it is sent back: %s", listed)
            request = f"{request}\n\nYour last merge's markers were wrong: {listed}. Write the merge again, with every pair of markers."
        return marked


def _get_spans(
    concepts: Sequence[SalientConceptCell], anchors_of_concept: dict[str, list[Anchor]], cell_id: str
) -> list[Span]:
    """The concepts' passages that stand in the cell, as spans of its text."""
    spans = []
    for concept in concepts:
        anchors = anchors_of_concept.get(concept.unique_id, [])
        for anchor in anchors:
            if anchor.cell_id == cell_id:
                span = Span(concept.title, anchor.start, anchor.end)
                spans.append(span)
    return spans


def _meets(scene: list[PlotNode], tag: tuple[str, list[str]]) -> bool:
    """Whether an event of this moment and place meets any event of the scene."""
    for event in scene:
        event_tag = get_tag(event)
        if tags_meet(event_tag, tag):
            return True
    return False


def _moment_of(scene: list[PlotNode]) -> tuple[int, tuple[int, ...], str]:
    """Where a scene stands on the clock: a moment of numbers, such as 3.1 or
    2.2.1, by its numbers; any other after all of those, by its text."""
    moment = scene[0].timestamp
    parts = moment.split(".")
    if all(part.isdigit() for part in parts):
        numbers = tuple(int(part) for part in parts)
        return (0, numbers, "")
    return (1, (), moment)
