"""The choices every scene the story goes on from ends with, written by the model:
the opening of a sentence the scene leaves unfinished, and an ending of it for
each edge leaving the scene's events, towards the event that edge leads to. The
opening is written from the scene and every event that could follow, and each
ending from the opening and its event alone. Every salient concept's passages
stay on the words of the scene they show.

The author reviews, and the model is shown, a scene's choices as its opening,
then its endings, numbered in the order of the edges:

    Varn's fingers tapped against her knee,
    1. as her phone rang with a call from mission control.
    2. as she watched the gripper close on the object.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from authordoc.cells.plot_cell import PlotEdge, PlotNode
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices, written_scene
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Confidence, Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.plot_ends import written_world_events
from story_generator.stages.scenes import (
    get_anchors,
    get_cell_of_event,
    get_scene_cell,
    get_scene_opening,
    get_scene_prose,
    get_scenes,
    with_words_pointed,
)

OPENING_INSTRUCTIONS = """You are the narrator of a story, and its only witness. You never take part in what happens and never mention yourself.

You are given the scene you have just told, and the events that could follow it. Each event starts with its moment and its place, like "3.1. [orbit]"; never mention these.

You are also given the story's plots, so that what you write agrees with them. Reveal nothing from them beyond the events you are given. When you are also given the author's comments on your earlier choices, answer every one of them.

Write only the opening of the next sentence, in the third person and the past tense, and stop in the middle of it, so that the sentence could be finished in a way that leads towards any one of those events. The opening must not lean towards one event more than the others, and must not tell what happens. Add no characters, places or events beyond those given.

For example, given:

The scene:
In a small café across the street, Bob sat alone at a table by the window. His coffee had gone cold. He turned his phone over in his hand, thinking of Alice.

What could happen next:
2.5. [city, café] Bob calls Alice to ask her to meet him.
2.5. [city, cinema] Alice and Mark leave the cinema together.

you write:

Bob stared at the screen of his phone,
"""

ENDING_INSTRUCTIONS = """You are the narrator of a story, and its only witness. You never take part in what happens and never mention yourself.

You are given the opening of a sentence, and one event that could follow. The event starts with its moment and its place, like "3.1. [orbit]"; never mention these.

You are also given the story's plots, so that what you write agrees with them. Reveal nothing from them beyond the event you are given. When you are also given the author's comments on your earlier choices, answer every one of them.

Write only the words that finish the sentence, in the third person and the past tense, so that it leads towards the event: it shows whom to follow, what to watch or where to go to see the event, but does not tell what happens. Do not repeat the opening. Add no characters, places or events beyond those given.

For example, given:

The opening:
Bob stared at the screen of his phone,

What could happen next:
2.5. [city, café] Bob calls Alice to ask her to meet him.

you write:

his thumb hovering over Alice's name.

And given the same opening, but:

What could happen next:
2.5. [city, cinema] Alice and Mark leave the cinema together.

you write:

while over the road, in the cinema, Alice and Mark's film was nearing its end.
"""

# Room for the opening or the ending of one sentence.
MAX_SENTENCE_PART_TOKENS = 64


def get_leaving(document: Document, scene: list[PlotNode]) -> tuple[list[PlotEdge], list[PlotNode]]:
    """The edges leaving the scene's events, in the order of the plots, and the
    event each of them leads to."""
    scene_ids = {event.node_id for event in scene}
    edges: list[PlotEdge] = []
    next_events: list[PlotNode] = []
    for plot in document.plots():
        for edge in plot.edges:
            if edge.from_node_id in scene_ids:
                next_event = plot.get_node_by_id(edge.to_node_id)
                edges.append(edge)
                next_events.append(next_event)
    return (edges, next_events)


def written_choices(opening: str, endings: list[str]) -> str:
    numbered = [f"{number}. {ending}" for number, ending in enumerate(endings, start=1)]
    listed = "\n".join(numbered)
    choices = f"{opening}\n{listed}"
    return choices


def read_choices(written: str) -> tuple[str, list[str]]:
    """The opening and the endings a draft lists."""
    opening, _, listed = written.partition("\n")
    endings = []
    for line in listed.splitlines():
        number, dot, ending = line.partition(". ")
        if dot and number.strip().isdigit():
            endings.append(ending.strip())
    return (opening.strip(), endings)


class Choices(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the choices: the scene's prose, and the
        # events its choices lead to.
        self.scene = ""
        self.leading_to: list[str] = []

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        confidence: Confidence = params["confidence"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots = written_world_events(document, "")
        going_on = []
        scenes_at_the_start = get_scenes(document)
        for index, scene in enumerate(scenes_at_the_start):
            edges, _ = get_leaving(document, scene)
            if edges:
                going_on.append(index)
        count = len(going_on)
        for done, index in enumerate(going_on):
            scenes = get_scenes(document)
            scene = scenes[index]
            held = get_scene_cell(document, scene)
            if held is None:
                logger.warning("the scene at %s is not told, so it has no choices yet", scene[0].timestamp)
                continue
            edges, next_events = get_leaving(document, scene)
            prose = get_scene_prose(held.source)
            self.scene = prose
            plots_leading_on = [document.get_plot_of_edge(edge) for edge in edges]
            self.leading_to = [f"{plot.title}: {event.summary}" for plot, event in zip(plots_leading_on, next_events)]
            self.progress = (done, count)
            held_choices = get_choices(held.source)
            held_opening = get_scene_opening(held.source)
            if held_opening is not None and all(edge.edge_id in held_choices for edge in edges):
                held_endings = [held_choices[edge.edge_id] for edge in edges]
                self.draft = written_choices(held_opening, held_endings)
            else:
                self.draft = self._drafted(plots, prose, next_events, [])

            def revised(comments: list[str]) -> str:
                choices = self._drafted(plots, prose, next_events, comments)
                return choices

            accepted = reviewed(self, renderer, revised, confidence, "choices")
            opening, endings = read_choices(accepted)
            by_edge = {edge.edge_id: ending for edge, ending in zip(edges, endings, strict=True)}
            source = written_scene(prose, opening, by_edge)
            cell_of_event = get_cell_of_event(document)
            # The choices follow the scene's prose, which keeps its characters, so
            # its passages stand where they stood.
            anchors_of_concept = get_anchors(document)
            scene_cell = held.with_source(source)
            cells = [scene_cell if cell.unique_id == held.unique_id else cell for cell in document.cells]
            written = Document.from_cells(cells, document.path)
            document = with_words_pointed(written, cell_of_event, anchors_of_concept)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (done + 1, count)
            logger.info("choices of scene %d of %d accepted", done + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_choices(self)
        return review

    def _drafted(self, plots: str, prose: str, next_events: list[PlotNode], comments: list[str]) -> str:
        """The scene's choices, drafted afresh, or, given the author's comments,
        written again to answer them."""
        options = [f"{event.timestamp}. [{event.location}] {event.summary}" for event in next_events]
        could_happen = "\n".join(options)
        commented = ""
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            commented = f"\n\nYour earlier choices:\n{self.draft}\n\nThe author's comments on them, oldest first:\n{written_comments}"
        opening_request = (
            f"The story's plots:\n{plots}\n\n"
            f"The scene:\n{prose}\n\nWhat could happen next:\n{could_happen}{commented}"
        )
        opening_written = self._model.complete(OPENING_INSTRUCTIONS, opening_request, MAX_SENTENCE_PART_TOKENS)
        opening = opening_written.strip()
        endings = []
        for option in options:
            ending_request = (
                f"The story's plots:\n{plots}\n\n"
                f"The opening:\n{opening}\n\nWhat could happen next:\n{option}{commented}"
            )
            ending_written = self._model.complete(ENDING_INSTRUCTIONS, ending_request, MAX_SENTENCE_PART_TOKENS)
            # A choice is written on one line.
            ending_words = ending_written.split()
            ending = " ".join(ending_words)
            endings.append(ending)
        choices = written_choices(opening, endings)
        return choices
