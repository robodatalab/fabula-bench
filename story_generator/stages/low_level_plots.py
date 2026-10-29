"""Each high-level plot expanded into its events, drafted by the model and kept in
the plot's cell, titled as its outline: every event with its moment on the
world's clock, its place, and a plain statement of what happens and why, each
caused by the one before.

The author reviews, and the model writes, a plot's events as a table, one event
a line, its moment, its place and what happens, separated by bars:

    0.2 | earth, a restaurant | He invites her to dinner.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.note_cell import NoteCell
from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.high_level_plots import get_acts, get_outline_overview, get_outline_title, get_outlines

INSTRUCTIONS = """You help an author write an interactive story in which many plots, each a full story of its own, mesh in one world.

You are given the high-level outline of one plot, the events of the plots the world already holds, and the acts of the world's clock. Expand the outline into the plot's events, every one caused by the one before it:

- Each event has a moment on the world's clock: the act and a step, as in 2.3. Where an event happens at the same time as another plot's event, use that event's moment. Put an event between two moments the world already uses with a sub-moment, as in 2.2.1; put what comes before the first act in act 0.
- Each event has a place, from the broadest to the most specific, separated by commas, as in "earth, Varn's house". Where an event happens in a place the world already has, use that place exactly.
- Each event is a plain, simple statement of what happens and why: no clock times, no invented places, nothing added for the mechanics of the story.
- A person is never in two places at one moment.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write one event a line, as: moment | place | what happens. Write the lines and nothing else."""

# Room for the events of one plot.
MAX_EVENTS_TOKENS = 3000

SEPARATOR = " | "


def written_events(events: Sequence[PlotNode]) -> str:
    lines = [SEPARATOR.join((event.timestamp, event.location, event.summary)) for event in events]
    table = "\n".join(lines)
    return table


def read_events(table: str, events_before: Sequence[PlotNode]) -> list[PlotNode]:
    """The events the table lists, in order. An event takes the id and the words
    of the event in the same place of the plot before, so that what pointed at
    that event points at it; an event past the end of the plot before is new. A
    line that is not an event is left out."""
    events: list[PlotNode] = []
    for line in table.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        written_moment, place, summary = [part.strip() for part in parts]
        moment = written_moment.lstrip("-* ")
        at = len(events)
        if at < len(events_before):
            event_before = events_before[at]
            event = replace(event_before, timestamp=moment, location=place, summary=summary)
        else:
            identifier = uuid4()
            event_id = str(identifier)
            event = PlotNode(event_id, None, moment, place, summary)
        events.append(event)
    return events


def chained(events: Sequence[PlotNode], edges_before: Sequence[PlotEdge]) -> list[PlotEdge]:
    """An edge from every event to the next, each taking the id of the edge in the
    same place of the plot before."""
    edges: list[PlotEdge] = []
    for at, (cause, effect) in enumerate(zip(events, events[1:])):
        if at < len(edges_before):
            edge_id = edges_before[at].edge_id
        else:
            identifier = uuid4()
            edge_id = str(identifier)
        edge = PlotEdge(edge_id, cause.node_id, effect.node_id)
        edges.append(edge)
    return edges


def written_world_events(document: Document, but: str) -> str:
    """Every plot's events, each plot under its title, but those of the plot
    titled `but`."""
    tables = []
    for plot in document.plots():
        if plot.title == but:
            continue
        table = written_events(plot.nodes)
        tables.append(f"### {plot.title}\n{table}")
    written = "\n\n".join(tables) or "None yet."
    return written


class LowLevelPlots(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # The outline under review, for the renderer to show.
        self.outline = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        outlines = get_outlines(document)
        count = len(outlines)
        for index, outline in enumerate(outlines):
            self.outline = outline.source
            self.progress = (index, count)
            title = get_outline_title(outline.source)
            plot = next((plot for plot in document.plots() if plot.title == title), None)
            self.draft = written_events(plot.nodes) if plot is not None else self._drafted(document, title, [])

            def revised(comments: list[str]) -> str:
                events = self._drafted(document, title, comments)
                return events

            accepted = reviewed(self, renderer, revised)
            if plot is not None:
                events = read_events(accepted, plot.nodes)
                edges = chained(events, plot.edges)
                plot_written = replace(plot, nodes=events, edges=edges)
                cells = [plot_written if cell.unique_id == plot.unique_id else cell for cell in document.cells]
            else:
                events = read_events(accepted, [])
                edges = chained(events, [])
                overview = get_outline_overview(outline.source)
                identifier = uuid4()
                plot_id = str(identifier)
                plot_written = PlotCell(title, events, edges, overview, False, None, plot_id)
                plots_and_notes_at = [at for at, cell in enumerate(document.cells) if isinstance(cell, (PlotCell, NoteCell))]
                after_them = plots_and_notes_at[-1] + 1 if plots_and_notes_at else 0
                cells = [*document.cells[:after_them], plot_written, *document.cells[after_them:]]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("plot %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_low_level_plots(self)
        return review

    def _drafted(self, document: Document, title: str, comments: list[str]) -> str:
        """The plot's events, drafted afresh from its outline, or, given the
        author's comments, the draft under review revised to answer them."""
        world = written_world_events(document, title)
        acts = get_acts(document)
        written_acts = ", ".join(acts)
        request = (
            f"The plot's outline:\n{self.outline}\n\n"
            f"The events of the world's plots so far:\n{world}\n\n"
            f"The acts of the world's clock: {written_acts}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_EVENTS_TOKENS)
        events = written.strip()
        return events
