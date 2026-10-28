"""The writer of a scene: a model given the place and the events of a scene, and
asked for the prose that shows them; then, given the events that could follow,
for the opening of a sentence the scene leaves unfinished and an ending of it
towards each of those events."""

from __future__ import annotations

from collections.abc import Sequence

from fabula_bench.benchmark_document import get_place
from fabula_bench.players.agent_player import CompletionModel
from authordoc.cells.plot_cell import PlotNode

SCENE_INSTRUCTIONS = """You write one scene of an interactive story, the way a text adventure such as Zork shows a location: whoever reads it may have come to it from anywhere in the story, so it stands on its own. It says nothing of what happened before it, and nothing of what may happen after it.

You are the story's narrator and its only witness: you never take part in what happens and never mention yourself. Write in the third person and the past tense.

You are given where the scene takes place and the events that happen there. When there are several, they happen at the same moment and in the same place, and the scene shows every one of them. Describe the place, and the people there: what they see, do and say. Show each event as it is given and nothing beyond it: add no named characters and no events of your own, though the people an event implies, such as a crew or a team of scientists, may be seen at their work.

Write two to four paragraphs of prose and nothing else: no title, no heading, no list."""

# Room for a scene of a few paragraphs.
MAX_SCENE_TOKENS = 1500

OPENING_INSTRUCTIONS = """You are the narrator of a story, and its only witness. You never take part in what happens and never mention yourself.

You are given the scene you have just told, and the events that could follow it. Each event starts with its moment and its place, like "3.1. [orbit]"; never mention these.

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


class SceneWriter:
    def __init__(self, model: CompletionModel) -> None:
        self._model = model

    def write(self, events: Sequence[PlotNode]) -> str:
        """The scene that shows these events, which happen together."""
        where = get_place(list(events))
        summaries = [f"- {event.summary}" for event in events]
        happening = "\n".join(summaries)
        request = f"Where the scene takes place: {where}\n\nWhat happens there:\n{happening}"
        scene = self._model.complete(SCENE_INSTRUCTIONS, request, MAX_SCENE_TOKENS)
        scene_written = scene.strip()
        return scene_written

    def write_choices(self, scene: str, next_events: Sequence[PlotNode]) -> tuple[str, list[str]]:
        """The opening of the sentence the scene leaves unfinished, and the endings
        of that sentence, one for each event that could follow, in their order.
        The opening is written from the scene and all the events that could
        follow, and each ending from the opening and its event alone."""
        options = [f"{event.timestamp}. [{event.location}] {event.summary}" for event in next_events]
        could_happen = "\n".join(options)
        opening_request = f"The scene:\n{scene}\n\nWhat could happen next:\n{could_happen}"
        opening_written = self._model.complete(OPENING_INSTRUCTIONS, opening_request, MAX_SENTENCE_PART_TOKENS)
        opening = opening_written.strip()
        endings = []
        for option in options:
            ending_request = f"The opening:\n{opening}\n\nWhat could happen next:\n{option}"
            ending_written = self._model.complete(ENDING_INSTRUCTIONS, ending_request, MAX_SENTENCE_PART_TOKENS)
            # A choice is written on one line.
            ending_words = ending_written.split()
            ending = " ".join(ending_words)
            endings.append(ending)
        return (opening, endings)
