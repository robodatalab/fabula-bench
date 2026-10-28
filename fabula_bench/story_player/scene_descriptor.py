"""The narrator: the story's only witness. It tells, in the third person and the
past tense, what happens where it is now, carrying on from what happened just
before, and leaves the next sentence open, with endings that lead towards what could
happen next without telling it, so that whoever plays finishes it as the narrator.

The narrator is a local model that vramen serves.
"""

from __future__ import annotations

from collections.abc import Sequence

from vramen import CausalModel

DESCRIPTION_MODEL = "Qwen/Qwen3-8B"

# What the model takes resident, declared against vramen's quota.
DESCRIPTION_MODEL_MEMORY_GB = 17.0

# Room for a description of a paragraph or two.
MAX_NEW_TOKENS = 512

# Room for the opening or the ending of one sentence.
MAX_SENTENCE_PART_TOKENS = 64

INSTRUCTIONS = """You are the narrator of a story, and its only witness. You never take part in what happens and never mention yourself, and you can be wherever an event takes place.

You are given where you are and whether the story moved there, what happened just before, and what is happening where you are now. Each event starts with its moment and its place, like "3.1. [orbit]"; never mention these. You stay where you are.

Tell, in the third person and the past tense, in one short paragraph, what happened where you are: the place, and what the people there did and said. Carry on from what happened just before, so that the story reads as one. If the story moved, begin with "Meanwhile," and the new place, as in "Meanwhile, on Mars, ...". If it stayed in the same place, carry straight on without naming the place again. Describe only what is happening now, and do not address anyone.

Refer to the characters by their names or by who they are. Add no characters, places or events beyond those given.

For example, given:

Where you are: city, café (the story moved here from city, cinema)

What happened just before:
2.3. [city, cinema] Alice and Mark watch a film together.

What is happening:
2.4. [city, café] Bob sits alone in a café, thinking of Alice.

you write:

In a small café across the street, Bob sat alone at a table by the window. His coffee had gone cold. He turned his phone over in his hand, thinking of Alice.

IF the location changes between the scenes, make sure to add a segue word, like "meanwhile".
"""

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


class SceneDescriptor:
    def __init__(self, narrator: CausalModel) -> None:
        self._narrator = narrator

    def describe(
        self,
        place: str,
        scene_texts: Sequence[str],
        option_texts: Sequence[str],
        previous_place: str | None,
        previous_scene_texts: Sequence[str] | None,
    ) -> tuple[str, list[str]]:
        """The scene made of these events, as seen from this place, carrying on
        from the events of the previous scene (None at the start of the story)
        and ending with the open next sentence, and the endings of that sentence,
        one for each event that could follow, in their order.

        The previous scene is given by its events, not by its description, so
        that whatever the narrator embellished there is not taken for a fact.
        The opening of the sentence is written from the scene and all the events
        that could follow, and each ending from the opening and its event alone."""
        scene = "\n".join(scene_texts)
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
            f"What is happening:\n{scene}"
        )
        scene_description = self._narrator.complete(INSTRUCTIONS, request, MAX_NEW_TOKENS)
        options = "\n".join(option_texts)
        opening_request = f"The scene:\n{scene_description}\n\nWhat could happen next:\n{options}"
        opening = self._narrator.complete(OPENING_INSTRUCTIONS, opening_request, MAX_SENTENCE_PART_TOKENS)
        endings = []
        for option_text in option_texts:
            ending_request = f"The opening:\n{opening}\n\nWhat could happen next:\n{option_text}"
            ending = self._narrator.complete(ENDING_INSTRUCTIONS, ending_request, MAX_SENTENCE_PART_TOKENS)
            endings.append(ending)
        description = f"{scene_description} {opening} _____ [fill the gap]:"
        return (description, endings)

