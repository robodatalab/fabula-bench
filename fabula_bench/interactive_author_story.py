"""An interactive story, kept in an `.author` document: everything the benchmark
and the story generator read from the document, or write into it, beyond its
storydoc format.

Every plot event has a timestamp and a location: the timestamp is a clock shared
by all the plots, and the location runs from the broadest place to the most
specific, as in "earth, Varn's house". Events at the same moment and in the same
place form one scene.

Every scene is told by a markdown cell, which every event of the scene points at.
A scene that the story goes on from ends with the opening of a sentence, left
unfinished, and the choices that finish it, one for each edge leaving the scene's
events, written as a list that names the edge each choice follows:

    Varn's fingers tapped against her knee, _____

    <ol title="choices">
    <li edge="x1">as her phone rang with a call from mission control.</li>
    <li edge="x2">as she watched the gripper close on the object.</li>
    </ol>

A plot references the salient concepts it illustrates, and keeps how each of them
shows at each of its events, its concept arcs, in a note after it:

    0.1 The politician meets Captain Varn, and starts pretending to like her.
      Classical romance: —
      Good beats evil: the evil side: he courts her only for what she can tell him.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.note_cell import NoteCell
from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from authordoc.written_attributes import attributes_in, written_attribute_value

# Marks the gap the choices fill, at the end of the sentence a scene leaves unfinished.
GAP = "_____"

_ATTRIBUTES = r'((?:\s+[A-Za-z0-9][A-Za-z0-9_-]*\s*=\s*"(?:[^"\\]|\\.)*")*)\s*'
_CHOICES_OPENED = '<ol title="choices">'
_CHOICE = re.compile(rf"^<li{_ATTRIBUTES}>(.*)</li>$")
_CHOICES_CLOSED = "</ol>"
_EDGE = "edge"

# Stands for a concept that does not show at an event.
ABSENT = "—"

# Heads the note a plot's arc is kept in, before the plot's title.
HEADING = "## Concept arcs of "


class InteractiveScene:
    """A scene, told by a markdown cell: its text, then the opening of a sentence it
    leaves unfinished at the gap, then the options that finish it, each by the id
    of the edge it follows. A scene the story ends at has neither."""

    def __init__(self, markdown_cell: MarkdownCell) -> None:
        self.markdown_cell = markdown_cell

    @property
    def markdown_cell_id(self) -> str:
        return self.markdown_cell.unique_id

    @property
    def text(self) -> str:
        scene_text, _, _ = self._read()
        return scene_text

    def with_text(self, scene_text: str) -> InteractiveScene:
        _, opening, options = self._read()
        scene = self._written(scene_text, opening, options)
        return scene

    @property
    def opening(self) -> str:
        """The opening of the sentence the scene leaves unfinished; empty for a
        scene that leaves none."""
        _, opening, _ = self._read()
        return opening

    def with_opening(self, opening: str) -> InteractiveScene:
        scene_text, _, options = self._read()
        scene = self._written(scene_text, opening, options)
        return scene

    @property
    def options(self) -> dict[str, str]:
        """The options that finish the sentence, each by the id of the edge it
        follows, in the order the scene lists them."""
        _, _, options = self._read()
        return options

    def with_options(self, options: dict[str, str]) -> InteractiveScene:
        scene_text, opening, _ = self._read()
        scene = self._written(scene_text, opening, options)
        return scene

    def _read(self) -> tuple[str, str, dict[str, str]]:
        """The cell's source parsed: the scene's text, its opening and its options."""
        told_to_the_gap, _, written_options = self.markdown_cell.source.partition(_CHOICES_OPENED)
        told = told_to_the_gap.strip()
        scene_text = told
        opening = ""
        if told.endswith(GAP):
            scene_text, _, unfinished = told.rpartition("\n\n")
            without_the_gap = unfinished.removesuffix(GAP)
            opening = without_the_gap.strip()
        options: dict[str, str] = {}
        for line in written_options.splitlines():
            written_option = _CHOICE.match(line)
            if written_option is None:
                continue
            written_attributes = written_option.group(1)
            attributes = attributes_in(written_attributes)
            edge_id = attributes[_EDGE]
            option = written_option.group(2)
            options[edge_id] = option
        return (scene_text, opening, options)

    def _written(self, scene_text: str, opening: str, options: dict[str, str]) -> InteractiveScene:
        """The scene with its cell's source written from its text, opening and
        options, as the schema writes them; what it lacks is left out."""
        parts = [scene_text] if scene_text else []
        if opening:
            parts.append(f"{opening} {GAP}")
        if options:
            written_options = [_CHOICES_OPENED]
            for edge_id, option in options.items():
                written_edge = written_attribute_value(edge_id)
                written_options.append(f'<li {_EDGE}="{written_edge}">{option}</li>')
            written_options.append(_CHOICES_CLOSED)
            options_list = "\n".join(written_options)
            parts.append(options_list)
        source = "\n\n".join(parts)
        cell = self.markdown_cell.with_source(source)
        scene = InteractiveScene(cell)
        return scene


class StoryArc:
    """How each concept a plot illustrates shows at each of its events, kept in a
    note cell: under a heading that names the plot, every event's moment and what
    happens, and under it, for every concept, how the concept shows there, or
    ABSENT where it does not."""

    def __init__(self, note_cell: NoteCell) -> None:
        self.note_cell = note_cell

    @property
    def notes_cell_id(self) -> str:
        return self.note_cell.unique_id

    @property
    def shows(self) -> list[dict[str, str]]:
        """For every event the arc lists, in order, how each concept that shows
        there shows, by the concept's title."""
        shows: list[dict[str, str]] = []
        for line in self._lines():
            if not line.startswith(" "):
                shows.append({})
                continue
            if not shows:
                continue
            written_title, _, how = line.partition(":")
            title = written_title.strip()
            shown = how.strip()
            if shown and shown not in (ABSENT, "-", "–"):
                shows[-1][title] = shown
        return shows

    @property
    def titles(self) -> list[str]:
        """The titles of the concepts the arc lists, in the order it first lists
        them, whether they show or not."""
        titles: list[str] = []
        for line in self._lines():
            if not line.startswith(" "):
                continue
            written_title, _, _ = line.partition(":")
            title = written_title.strip()
            if title not in titles:
                titles.append(title)
        return titles

    def with_shows(self, plot: PlotCell, titles: Sequence[str], shows: Sequence[dict[str, str]]) -> StoryArc:
        """The arc written for the plot: for every event, how each of the concepts
        shows there, ABSENT where it does not."""
        lines = [f"{HEADING}{plot.title}", ""]
        for event, shown in zip(plot.nodes, shows):
            lines.append(f"{event.timestamp} {event.summary}")
            for title in titles:
                how = shown.get(title) or ABSENT
                lines.append(f"  {title}: {how}")
        source = "\n".join(lines)
        cell = self.note_cell.with_source(source)
        arc = StoryArc(cell)
        return arc

    def _lines(self) -> list[str]:
        """The note's lines that list the events and the concepts: not its heading,
        nor its blank lines."""
        lines = self.note_cell.source.splitlines()
        listed = [line for line in lines if line.strip() and not line.startswith("#")]
        return listed


class InteractiveAuthorStory:
    """An interactive story, kept in `document`."""

    def __init__(self, document: Document) -> None:
        self.document = document

    @property
    def scenes(self) -> list[InteractiveScene]:
        """Every markdown cell that tells an event, as a scene, in the order of the
        cells; a markdown cell no event points at tells no scene."""
        first_words = {
            event.story_word_range.first_word
            for plot in self.document.plots()
            for event in plot.nodes
            if event.story_word_range is not None
        }
        story_words = StoryWordsIterator(self.document)
        telling = {word.cell_id for word in story_words if word.number in first_words}
        scenes = [
            InteractiveScene(cell)
            for cell in self.document.cells
            if isinstance(cell, MarkdownCell) and cell.unique_id in telling
        ]
        return scenes

    def with_scenes(self, scenes: Sequence[InteractiveScene]) -> InteractiveAuthorStory:
        """The story with these scenes in it: a scene whose cell the story has takes
        that cell's place, and one it does not have comes after its last cell."""
        cell_of_id = {scene.markdown_cell_id: scene.markdown_cell for scene in scenes}
        ids_held = {cell.unique_id for cell in self.document.cells}
        cells = [cell_of_id.get(cell.unique_id, cell) for cell in self.document.cells]
        added = [scene.markdown_cell for scene in scenes if scene.markdown_cell_id not in ids_held]
        document = Document.from_cells([*cells, *added], self.document.path)
        story = InteractiveAuthorStory(document)
        return story

    def scene_of(self, event: PlotNode) -> InteractiveScene | None:
        """The scene that tells the event: the one whose cell holds the event's
        first word; None for an event no scene tells."""
        if event.story_word_range is None:
            return None
        first_word = event.story_word_range.first_word
        story_words = StoryWordsIterator(self.document)
        cell_ids = [word.cell_id for word in story_words if word.number == first_word]
        if not cell_ids:
            return None
        cell_id, *_ = cell_ids
        cell = self.document.cell_with_id(cell_id)
        if not isinstance(cell, MarkdownCell):
            return None
        scene = InteractiveScene(cell)
        return scene

    def events_of(self, scene: InteractiveScene) -> list[PlotNode]:
        """The events the scene tells: every event whose first word is in its cell,
        in the order of the plots."""
        story_words = StoryWordsIterator(self.document)
        numbers = {word.number for word in story_words if word.cell_id == scene.markdown_cell_id}
        events = [
            event
            for plot in self.document.plots()
            for event in plot.nodes
            if event.story_word_range is not None and event.story_word_range.first_word in numbers
        ]
        return events

    @property
    def arcs(self) -> list[StoryArc]:
        """Every plot's arc, in the order of the plots; a plot without one has none."""
        arcs = []
        for plot in self.document.plots():
            arc = self.arc_of(plot)
            if arc is not None:
                arcs.append(arc)
        return arcs

    def arc_of(self, plot: PlotCell) -> StoryArc | None:
        """The plot's arc: the note whose id the plot's own id gives; None for a plot
        without one."""
        note_id = self._arc_id(plot)
        note = self.document.cell_with_id(note_id)
        if not isinstance(note, NoteCell):
            return None
        arc = StoryArc(note)
        return arc

    def with_arc(self, plot: PlotCell, arc: StoryArc) -> InteractiveAuthorStory:
        """The story with the arc as the plot's: in place of the plot's arc, or right
        after the plot when it has none."""
        note_id = self._arc_id(plot)
        note = replace(arc.note_cell, _unique_id=note_id)
        held = self.document.cell_with_id(note_id)
        cells = []
        for cell in self.document.cells:
            if cell.unique_id == note_id:
                cells.append(note)
                continue
            cells.append(cell)
            if held is None and cell.unique_id == plot.unique_id:
                cells.append(note)
        document = Document.from_cells(cells, self.document.path)
        story = InteractiveAuthorStory(document)
        return story

    def _arc_id(self, plot: PlotCell) -> str:
        """The id of the note the plot's arc is kept in: the same for the plot every
        time, so that the arc is found again."""
        arc_uuid = uuid5(NAMESPACE_URL, f"fabula-bench/concept arcs/{plot.unique_id}")
        note_id = str(arc_uuid)
        return note_id
