"""The choices every scene the story goes on from ends with, written by the model:
the opening of a sentence the scene leaves unfinished, and an ending of it for
each edge leaving the scene's events, towards the event that edge leads to. The
opening is written from the scene and every event that could follow, and each
ending from the opening and its event alone.

The author reviews a scene's choices as its opening, then its endings, numbered
in the order of the edges:

    Varn's fingers tapped against her knee,
    1. as her phone rang with a call from mission control.
    2. as she watched the gripper close on the object.
"""

from __future__ import annotations

from authordoc.cells.plot_cell import PlotEdge, PlotNode
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory, InteractiveScene
from fabula_bench.players.agent_player import CompletionModel
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stage import Stage, StageStep

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


def _written_choices(opening: str, endings: list[str]) -> str:
    numbered = [f"{number}. {ending}" for number, ending in enumerate(endings, start=1)]
    listed = "\n".join(numbered)
    choices = f"{opening}\n{listed}"
    return choices


class ChoicesStep(StageStep):
    """The choices one scene ends with: an ending for each edge leaving its events."""

    def __init__(self, scene: InteractiveScene, edges: list[PlotEdge], model: CompletionModel) -> None:
        self._scene = scene
        self._edges = edges
        self._model = model

    def __call__(self, document: Document, reviews: TerminalReview, reviewer_instruction: str) -> tuple[ReviewResult, Document]:
        story = InteractiveAuthorStory(document)
        plots = story.written_world_events("")
        next_events: list[PlotNode] = []
        for edge in self._edges:
            plot = document.get_plot_of_edge(edge)
            next_event = plot.get_node_by_id(edge.to_node_id)
            next_events.append(next_event)
        options = [f"{event.timestamp}. [{event.location}] {event.summary}" for event in next_events]
        could_happen = "\n".join(options)
        asked = f"\n\nThe author asks you to do it again: {reviewer_instruction}" if reviewer_instruction else ""

        opening_request = (
            f"The story's plots:\n{plots}\n\n"
            f"The scene:\n{self._scene.text}\n\nWhat could happen next:\n{could_happen}{asked}"
        )
        opening_written = self._model.complete(OPENING_INSTRUCTIONS, opening_request, MAX_SENTENCE_PART_TOKENS)
        opening = opening_written.strip()

        endings = []
        for option in options:
            ending_request = (
                f"The story's plots:\n{plots}\n\n"
                f"The opening:\n{opening}\n\nWhat could happen next:\n{option}{asked}"
            )
            ending_written = self._model.complete(ENDING_INSTRUCTIONS, ending_request, MAX_SENTENCE_PART_TOKENS)
            # A choice is written on one line.
            ending_words = ending_written.split()
            ending = " ".join(ending_words)
            endings.append(ending)

        choices = _written_choices(opening, endings)
        review_result = reviews(self._scene.text, could_happen, choices)
        if not review_result.is_passed():
            return review_result, document

        edge_endings = zip(self._edges, endings, strict=True)
        by_edge = {edge.edge_id: ending for edge, ending in edge_endings}
        opened = self._scene.with_opening(opening)
        scene = opened.with_options(by_edge)
        story = story.with_scenes([scene])

        return review_result, story.document


class Choices(Stage):

    def __init__(self, model: CompletionModel) -> None:
        self._model = model

    def run(self, document: Document) -> list[StageStep]:
        story = InteractiveAuthorStory(document)

        choices_steps: list[StageStep] = []
        for scene in story.scenes:
            events = story.events_of(scene)
            edges: list[PlotEdge] = []
            for event in events:
                plot = document.get_plot_of_node(event)
                outbound = plot.outbound_edges(event)
                edges.extend(outbound)
            # The story ends at a scene no edge leaves: it has no choices.
            if not edges:
                continue
            choices_step = ChoicesStep(scene, edges, self._model)
            choices_steps.append(choices_step)

        return choices_steps
