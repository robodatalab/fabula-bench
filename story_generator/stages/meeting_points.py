"""The plots meshed into one world. For each plot in turn, the model revises its
events' moments and places, seeing every other plot's, so that none of its
people is in two places at one moment and it meets the other plots where their
people come together; the author reviews the revision beside where the plot
meets the others now."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from authordoc.cells.plot_cell import PlotCell
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_place
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.low_level_plots import chained, read_events, written_events, written_world_events
from story_generator.stages.scenes import get_scenes

INSTRUCTIONS = """You help an author mesh the plots of an interactive story into one world.

Every event of a plot has a moment on the world's clock (the act and a step, as in 2.3; a sub-moment such as 2.2.1 falls between two moments; act 0 comes before the first act) and a place, from the broadest to the most specific, as in "earth, Varn's house". Events at the same moment, in places one of which holds the other, are one scene: that is where plots meet.

You are given every other plot's events, and the events of one plot to revise. Revise that plot's moments and places, so that:

- none of its people is in two places at one moment, in this plot or across the plots;
- it meets the other plots where their people come together, at the same moment and in the same place;
- its events stay in the order they happen.

Change what an event says only where its new moment or place no longer fits it. Keep every event, and add none. If the plot needs no change, write it as it is.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write one event a line, as: moment | place | what happens. Write the lines and nothing else."""

# Room for the events of one plot.
MAX_EVENTS_TOKENS = 3000


def get_meetings(document: Document, plot: PlotCell) -> str:
    """Where the plot meets the other plots: every scene its events share with
    theirs, by moment and place, one a line."""
    title_of_event = {event.node_id: other.title for other in document.plots() for event in other.nodes}
    own_ids = {event.node_id for event in plot.nodes}
    lines = []
    for scene in get_scenes(document):
        scene_ids = {event.node_id for event in scene}
        others = sorted({title_of_event[event_id] for event_id in scene_ids - own_ids})
        if not own_ids & scene_ids or not others:
            continue
        place = get_place(scene)
        written_others = ", ".join(others)
        lines.append(f"{scene[0].timestamp} | {place} | with {written_others}")
    meetings = "\n".join(lines) or "It meets no other plot."
    return meetings


class MeetingPoints(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the revision: the plot, its events as
        # they are, and where it meets the other plots now.
        self.title = ""
        self.events_now = ""
        self.meetings = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots_at_the_start = document.plots()
        count = len(plots_at_the_start)
        for index in range(count):
            plots = document.plots()
            plot = plots[index]
            self.title = plot.title
            self.events_now = written_events(plot.nodes)
            self.meetings = get_meetings(document, plot)
            self.progress = (index, count)
            self.draft = self._drafted(document, plot, [])

            def revised(comments: list[str]) -> str:
                events = self._drafted(document, plot, comments)
                return events

            accepted = reviewed(self, renderer, revised)
            events = read_events(accepted, plot.nodes)
            edges = chained(events, plot.edges)
            plot_meshed = replace(plot, nodes=events, edges=edges)
            cells = [plot_meshed if cell.unique_id == plot.unique_id else cell for cell in document.cells]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("plot %d of %d meshed", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_meeting_points(self)
        return review

    def _drafted(self, document: Document, plot: PlotCell, comments: list[str]) -> str:
        """The plot's events revised to mesh with the others, or, given the
        author's comments, the draft under review revised to answer them."""
        world = written_world_events(document, plot.title)
        request = f"The events of every other plot:\n{world}\n\nThe plot to revise, {plot.title}:\n{self.events_now}"
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_EVENTS_TOKENS)
        events = written.strip()
        return events
