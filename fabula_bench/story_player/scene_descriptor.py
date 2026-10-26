"""The narrator: the story's only witness. It tells, in the third person and the
past tense, what happens where it is now, carrying on from what happened just
before, and notices what points to what could happen next without telling it, so that
whoever plays says, as the narrator, where to go.

The narrator is a local model, so vramen deploys and manages it.
"""

from __future__ import annotations

from collections.abc import Sequence

from vramen import CausalModel, InferenceModelResourceManager, qwen_chat_prompt

DESCRIPTION_MODEL = "Qwen/Qwen3-8B"

# What the model takes resident, declared against vramen's quota.
DESCRIPTION_MODEL_MEMORY_GB = 17.0

# Room for a description of a paragraph or two.
MAX_NEW_TOKENS = 512

INSTRUCTIONS = """You are the narrator of a story, and its only witness. You never take part in what happens and never mention yourself, and you can be wherever an event takes place.

You are given where you are and whether the story moved there, what happened just before, what is happening where you are now, and the events that could follow. Each event starts with its moment and its place, like "3.1. [orbit]"; never mention these. You stay where you are.

Tell, in the third person and the past tense, in one short paragraph, what happened where you are: the place, and what the people there did and said. Carry on from what happened just before, so that the story reads as one. If the story moved, begin with "Meanwhile," and the new place, as in "Meanwhile, on Mars, ...". If it stayed in the same place, carry straight on without naming the place again. Describe only what is happening now. The events that could follow may take place elsewhere; for each of them, mention something seen or heard here that points towards it, without telling what happens. Do not list or number the possibilities, and do not address anyone.

Refer to the characters by their names or by who they are. Add no characters, places or events beyond those given.

For example, given:

Where you are: city, café (the story moved here from city, cinema)

What happened just before:
2.3. [city, cinema] Alice and Mark watch a film together.

What is happening:
2.4. [city, café] Bob sits alone in a café, thinking of Alice.

What could happen next:
2.5. [city, café] Bob calls Alice to ask her to meet him.
2.5. [city, cinema] Alice and Mark leave the cinema together.

you write:

In a small café across the street, Bob sat alone at a table by the window. His coffee had gone cold. He turned his phone over in his hand; twice he opened Alice's name on the screen, and twice he put the phone down. Outside, the lights of the cinema flickered as the evening show let out.

IF the location changes between the scenes, make sure to add a segue word, like "meanwhile".
"""


class SceneDescriptor:
    def __init__(self, manager: InferenceModelResourceManager) -> None:
        self._narrator = CausalModel(
            DESCRIPTION_MODEL,
            qwen_chat_prompt,
            manager,
            mem_required_gb=DESCRIPTION_MODEL_MEMORY_GB,
        )

    def describe(
        self,
        place: str,
        scene_texts: Sequence[str],
        option_texts: Sequence[str],
        previous_place: str | None,
        previous_scene_texts: Sequence[str] | None,
    ) -> str:
        """The scene made of these events, as seen from this place, carrying on
        from the events of the previous scene (None at the start of the story)
        and hinting at the events that could follow.

        The previous scene is given by its events, not by its description, so
        that whatever the narrator embellished there is not taken for a fact."""
        scene = "\n".join(scene_texts)
        options = "\n".join(option_texts)
        if previous_place is None:
            movement = "this is where the story begins"
        elif previous_place == place:
            movement = "the story stayed in the same place"
        else:
            movement = f"the story moved here from {previous_place}"
        if previous_scene_texts is None:
            before = "Nothing: this is where the story begins."
        else:
            before = "\n".join(previous_scene_texts)
        request = (
            f"Where you are: {place} ({movement})\n\n"
            f"What happened just before:\n{before}\n\n"
            f"What is happening:\n{scene}\n\nWhat could happen next:\n{options}"
        )
        description = self._narrator.complete(INSTRUCTIONS, request, MAX_NEW_TOKENS)
        return description
