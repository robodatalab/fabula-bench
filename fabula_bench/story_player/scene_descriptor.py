"""The narrator: describes the scene the player is in, hinting at what could
happen next without listing it, so that the player says in their own words
what they want to do.

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

INSTRUCTIONS = """You narrate an interactive story to a player who is present, unseen, at one moment of it.

You are given what is happening at this moment and place, and the events that could follow it. Each event starts with its moment and its place, like "3.1. [orbit]"; never mention these.

Describe the scene to the player in the second person and the present tense, in one or two short paragraphs: what they see and hear, and what the people there do and say. Let each event that could follow show through as a hint the player can pick up on and choose to follow. Do not list, number or announce the choices, do not tell what happens next, and do not ask the player what they do.

Use only what the events say. Do not invent names, places or events."""


class SceneDescriptor:
    def __init__(self, manager: InferenceModelResourceManager) -> None:
        self._narrator = CausalModel(
            DESCRIPTION_MODEL,
            qwen_chat_prompt,
            manager,
            mem_required_gb=DESCRIPTION_MODEL_MEMORY_GB,
        )

    def describe(self, scene_texts: Sequence[str], option_texts: Sequence[str]) -> str:
        """The scene made of these events, hinting at the events that could follow."""
        scene = "\n".join(scene_texts)
        options = "\n".join(option_texts)
        request = f"What is happening:\n{scene}\n\nWhat could happen next:\n{options}"
        description = self._narrator.complete(INSTRUCTIONS, request, MAX_NEW_TOKENS)
        return description
