"""The writer of a scene: a model given the place and the events of a scene, and
asked for the prose that shows them."""

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
