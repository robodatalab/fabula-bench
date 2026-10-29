"""A scene for every group of events that meet, written by the model and kept in
a markdown cell that every event of the scene points at, the whole of it.

Events meet when they happen at the same moment, in places one of which holds
the other. A scene's words are numbered with the story's, so writing a scene
moves the words of every scene after it: every event is then pointed again at
the whole of the cell that tells it, and the salient concepts lose their
passages, which are annotated last, on the finished scenes."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from authordoc.cells.cell import Cell
from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import GAP, get_place, get_scene_text, get_tag, tags_meet
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.high_level_plots import get_outlines

INSTRUCTIONS = """You write one scene of an interactive story, the way a text adventure such as Zork shows a location: whoever reads it may have come to it from anywhere in the story, so it stands on its own. It says nothing of what happened before it, and nothing of what may happen after it.

You are the story's narrator and its only witness: you never take part in what happens and never mention yourself. Write in the third person and the past tense.

You are given an outline of the story's plots, so that the scene agrees with them: who its people are, where they are, and how they reach one another. Use the outline for that alone, and show nothing from it beyond the events of this scene.

You are given where the scene takes place and the events that happen there. When there are several, they happen at the same moment and in the same place, and the scene shows every one of them. Describe the place, and the people there: what they see, do and say. Show each event as it is given and nothing beyond it: add no named characters and no events of your own, though the people an event implies, such as a crew or a team of scientists, may be seen at their work.

When you are also given your draft of the scene and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write two to four paragraphs of prose and nothing else: no title, no heading, no list."""

# Room for a scene of a few paragraphs.
MAX_SCENE_TOKENS = 1500


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


def with_events_told(document: Document, cell_of_event: dict[str, str]) -> Document:
    """The document with every event in `cell_of_event` pointed at the whole of
    the cell that tells it, wherever that cell's words now stand, every other
    event untold, and no salient concept annotated."""
    numbers_of_cell: dict[str, list[int]] = {}
    for word in StoryWordsIterator(document):
        numbers = numbers_of_cell.setdefault(word.cell_id, [])
        numbers.append(word.number)
    cells: list[Cell] = []
    for cell in document.cells:
        if isinstance(cell, SalientConceptCell):
            unannotated = replace(cell, references=[])
            cells.append(unannotated)
            continue
        if not isinstance(cell, PlotCell):
            cells.append(cell)
            continue
        events = []
        for event in cell.nodes:
            cell_id = cell_of_event.get(event.node_id)
            numbers = numbers_of_cell.get(cell_id, []) if cell_id is not None else []
            words = StoryWordRange(numbers[0], numbers[-1]) if numbers else None
            told = replace(event, story_word_range=words)
            events.append(told)
        plot_told = replace(cell, nodes=events)
        cells.append(plot_told)
    story = Document.from_cells(cells, document.path)
    return story


class Scenes(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the scene: when and where it happens,
        # and what happens in it.
        self.moment = ""
        self.place = ""
        self.happening: list[str] = []

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        outlines = get_outlines(document)
        outline = "\n\n".join(note.source for note in outlines)
        scenes_at_the_start = get_scenes(document)
        count = len(scenes_at_the_start)
        for index in range(count):
            # The scenes are taken from the story as it now stands, so that their
            # events point at the words they now have.
            scenes = get_scenes(document)
            scene = scenes[index]
            self.moment = scene[0].timestamp
            self.place = get_place(scene)
            self.happening = [event.summary for event in scene]
            self.progress = (index, count)
            held = get_scene_cell(document, scene)
            self.draft = get_scene_prose(held.source) if held is not None else self._drafted(outline, [])

            def revised(comments: list[str]) -> str:
                prose = self._drafted(outline, comments)
                return prose

            accepted = reviewed(self, renderer, revised)
            cell_of_event = get_cell_of_event(document)
            if held is not None:
                scene_cell = held.with_source(accepted)
                cells = [scene_cell if cell.unique_id == held.unique_id else cell for cell in document.cells]
            else:
                scene_cell = MarkdownCell(source=accepted)
                cells = [*document.cells, scene_cell]
            for event in scene:
                cell_of_event[event.node_id] = scene_cell.unique_id
            written = Document.from_cells(cells, document.path)
            document = with_events_told(written, cell_of_event)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("scene %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_scenes(self)
        return review

    def _drafted(self, outline: str, comments: list[str]) -> str:
        """The scene, drafted afresh, or, given the author's comments, the draft
        under review revised to answer them."""
        happening = "\n".join(f"- {summary}" for summary in self.happening)
        request = (
            f"The story's outline:\n{outline}\n\n"
            f"Where the scene takes place: {self.place}\n\nWhat happens there:\n{happening}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = (
                f"{request}\n\nYour draft of the scene:\n{self.draft}\n\n"
                f"The author's comments, oldest first:\n{written_comments}"
            )
        written = self._model.complete(INSTRUCTIONS, request, MAX_SCENE_TOKENS)
        prose = written.strip()
        return prose


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
