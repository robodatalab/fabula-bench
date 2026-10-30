"""For every concept, the plot that illustrates it, begun as two events: the one it
starts with and the goal it reaches. The plot is titled as its concept, and
stands after the concepts, in their order; the mesh adds the events between its
ends.

A plot names the concepts it illustrates on a line of its overview, as in
"Illustrates: Motherhood, The promise": a plot begun here illustrates its own
concept, and a plot written otherwise may illustrate several. A concept a plot
already illustrates has its plot; a plot that illustrates no concept the story
still has is gone.

The author reviews, and the model writes, a plot's ends, and every table of
events after them, one event a line, its moment on the world's clock, its place
and what happens, separated by bars:

    1 | earth, Varn's house | Varn is given command of a ship bound for Mars.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Confidence, Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.concepts import written_concepts

INSTRUCTIONS = """You help an author write an interactive story in which many plots, each a full story of its own, mesh in one world. The story is built from its salient concepts: every concept gets a plot that illustrates it, and every plot respects every concept, so that a character who is a mother acts as a mother in whichever plot she appears.

You are given the story's concepts, the plots written so far, and the concept whose plot to begin. Write the plot's two ends: the event it starts with and the goal it reaches, chosen so that the plot, once the events between them are added, illustrates its concept.

- Each event has a moment on the world's clock: numbers separated by dots, as in 2.3, where a greater moment is a later one. Leave room between the two ends for the events that will be added between them.
- Each event has a place, from the broadest to the most specific, separated by commas, as in "earth, Varn's house". Where an event happens in a place the world already has, use that place exactly.
- Each event is a plain, simple statement of what happens and why.
- Where the plot's people are the people of other plots, keep them as those plots have them.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write two lines, the start and then the goal, each as: moment | place | what happens. Write the lines and nothing else."""

# Room for a plot's two ends.
MAX_ENDS_TOKENS = 500

SEPARATOR = " | "

# Opens the line of a plot's overview that names the concepts it illustrates.
ILLUSTRATES = "Illustrates: "


def get_illustrated(plot: PlotCell) -> list[str]:
    """The titles of the concepts the plot illustrates, as its overview names them."""
    for line in plot.overview.splitlines():
        if line.startswith(ILLUSTRATES):
            listed = line.removeprefix(ILLUSTRATES)
            parts = listed.split(",")
            titles = [part.strip() for part in parts if part.strip()]
            return titles
    return []


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


class PlotEnds(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the ends: the concept the plot
        # illustrates.
        self.concept = ""
        self.description = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        confidence: Confidence = params["confidence"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        concepts = document.salient_concepts()
        titles = {concept.title for concept in concepts}
        kept = []
        for cell in document.cells:
            if isinstance(cell, PlotCell):
                illustrated = get_illustrated(cell)
                if not titles.intersection(illustrated):
                    continue
            kept.append(cell)
        document = Document.from_cells(kept, document.path)
        story.write_text(document.text, encoding="utf-8")
        count = len(concepts)
        # A plot that illustrates several concepts is begun once.
        begun: set[str] = set()
        for index, concept in enumerate(concepts):
            self.concept = concept.title
            self.description = concept.source
            self.progress = (index, count)
            plots = document.plots()
            plot = next((plot for plot in plots if concept.title in get_illustrated(plot)), None)
            if plot is not None and plot.unique_id in begun:
                continue
            held_ends = _get_ends(plot) if plot is not None else []
            self.draft = written_events(held_ends) if held_ends else self._drafted(document, [])

            def revised(comments: list[str]) -> str:
                ends = self._drafted(document, comments)
                return ends

            accepted = reviewed(self, renderer, revised, confidence, "plot ends")
            if plot is not None:
                start, *rest = read_events(accepted, held_ends)
                # The events the mesh added between the ends stay between them.
                between = plot.nodes[1:-1]
                events = [start, *between, *rest[-1:]]
                edges = chained(events, plot.edges)
                plot_written = replace(plot, nodes=events, edges=edges)
                cells = [plot_written if cell.unique_id == plot.unique_id else cell for cell in document.cells]
            else:
                events = read_events(accepted, [])
                edges = chained(events, [])
                identifier = uuid4()
                plot_id = str(identifier)
                overview = f"{ILLUSTRATES}{concept.title}"
                plot_written = PlotCell(concept.title, events, edges, overview, False, None, plot_id)
                concepts_and_plots_at = [
                    at for at, cell in enumerate(document.cells) if isinstance(cell, (SalientConceptCell, PlotCell))
                ]
                after_them = concepts_and_plots_at[-1] + 1 if concepts_and_plots_at else 0
                cells = [*document.cells[:after_them], plot_written, *document.cells[after_them:]]
            begun.add(plot_written.unique_id)
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("plot %d of %d begun", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_plot_ends(self)
        return review

    def _drafted(self, document: Document, comments: list[str]) -> str:
        """The plot's ends, drafted afresh, or, given the author's comments, the
        draft under review revised to answer them."""
        concepts = document.salient_concepts()
        written = written_concepts(concepts)
        world = written_world_events(document, self.concept)
        request = (
            f"The story's concepts:\n{written}\n\n"
            f"The plots written so far:\n{world}\n\n"
            f"The concept whose plot to begin, {self.concept}:\n{self.description}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        drafted = self._model.complete(INSTRUCTIONS, request, MAX_ENDS_TOKENS)
        ends = drafted.strip()
        return ends


def _get_ends(plot: PlotCell) -> list[PlotNode]:
    """The plot's first and last events: one, for a plot of one event; none, for a
    plot of none."""
    if len(plot.nodes) < 2:
        ends = list(plot.nodes)
        return ends
    first, *_, last = plot.nodes
    ends = [first, last]
    return ends
