"""Every plot filled in between its two ends, one plot after another, so that it
illustrates its concepts and meshes with the other plots: where its people come
together with theirs, its events take their moments and places, and so share
their scenes. The author reviews each plot beside where it meets the others
now."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from authordoc.cells.plot_cell import PlotCell
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_place
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Confidence, Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.concepts import written_concepts
from story_generator.stages.plot_ends import chained, get_illustrated, read_events, written_events, written_world_events
from story_generator.stages.scenes import get_scenes

INSTRUCTIONS = """You help an author mesh the plots of an interactive story into one world. The story is built from its salient concepts: every concept has a plot that illustrates it, and every plot respects every concept, so that a character who is a mother acts as a mother in whichever plot she appears.

Every event of a plot has a moment on the world's clock (numbers separated by dots, as in 2.3; a moment such as 2.3.1 falls between 2.3 and 2.4) and a place, from the broadest to the most specific, as in "earth, Varn's house". Events at the same moment, in places one of which holds the other, are one scene: that is where plots meet.

You are given the story's concepts, the events of the other plots, and the plot to fill in: the concepts it illustrates, and its events so far, from the one it starts with to the goal it reaches. Add the events between them, so that:

- the plot illustrates its concepts, every event caused by the one before it;
- where the plot's people come together with another plot's, its event takes the moment and the place of that plot's event, so that the two plots meet in one scene;
- none of its people is in two places at one moment, in this plot or across the plots;
- the first and the last events stay as they are.

Each event is a plain, simple statement of what happens and why: no clock times, no invented places, nothing added for the mechanics of the story.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write every event of the plot, the first and the last included, one a line, as: moment | place | what happens. Write the lines and nothing else."""

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


class Mesh(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the plot: its title, the concepts it
        # illustrates, its events as they are, and where it meets the other plots
        # now.
        self.plot = ""
        self.concepts = ""
        self.description = ""
        self.events_now = ""
        self.meetings = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        confidence: Confidence = params["confidence"]
        checkpoint: Callable[[], None] = params["checkpoint"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots_at_the_start = document.plots()
        count = len(plots_at_the_start)
        for index in range(count):
            plots = document.plots()
            plot = plots[index]
            concepts = document.salient_concepts()
            illustrated = get_illustrated(plot)
            descriptions = [f"{concept.title}: {concept.source}" for concept in concepts if concept.title in illustrated]
            self.plot = plot.title
            self.concepts = ", ".join(illustrated) or "no concept"
            self.description = "\n".join(descriptions)
            self.events_now = written_events(plot.nodes)
            self.meetings = get_meetings(document, plot)
            self.progress = (index, count)
            # A plot of more events than its ends has been filled in before.
            self.draft = self.events_now if len(plot.nodes) > 2 else self._drafted(document, [])

            def revised(comments: list[str]) -> str:
                events = self._drafted(document, comments)
                return events

            accepted = reviewed(self, renderer, revised, confidence, "mesh")
            events = read_events(accepted, plot.nodes)
            edges = chained(events, plot.edges)
            plot_meshed = replace(plot, nodes=events, edges=edges)
            cells = [plot_meshed if cell.unique_id == plot.unique_id else cell for cell in document.cells]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            checkpoint()
            self.progress = (index + 1, count)
            logger.info("plot %d of %d meshed", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_mesh(self)
        return review

    def _drafted(self, document: Document, comments: list[str]) -> str:
        """The plot's events, filled in between its ends, or, given the author's
        comments, the draft under review revised to answer them."""
        concepts = document.salient_concepts()
        written = written_concepts(concepts)
        world = written_world_events(document, self.plot)
        request = (
            f"The story's concepts:\n{written}\n\n"
            f"The events of the other plots:\n{world}\n\n"
            f"The plot to fill in, {self.plot}, which illustrates {self.concepts}:\n{self.events_now}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        drafted = self._model.complete(INSTRUCTIONS, request, MAX_EVENTS_TOKENS)
        events = drafted.strip()
        return events
