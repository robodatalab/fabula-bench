"""Playing an environment with a local model that vramen serves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fabula_bench.story_player.story_player import StoryPlayer


class CompletionModel(Protocol):
    """Whatever completes one message: a vramen `CausalModel`, or `ClaudeModel`."""

    def complete(self, system: str, user: str, max_new_tokens: int) -> str: ...

PLAY_INSTRUCTIONS = """You are playing an interactive story. You are its narrator: \
its only witness, who never takes part in what happens. Scene by scene, you are \
told what happened, and each scene stops in the middle of a sentence. Choose how \
that sentence goes on from its numbered endings: the story goes where the ending \
you choose leads. You are given the play so far, ending with the scene you are \
choosing in. Answer with the number of the ending and nothing else."""

# Room for the number of an ending.
MAX_NEW_TOKENS = 16

ASK_INSTRUCTIONS = """You have just played an interactive story as its narrator. \
You are given the play, and then a question about the story. Answer the question."""

# Room for an answer of a few sentences.
MAX_ANSWER_TOKENS = 256


class AgentPlayer:
    """Gives the model the play so far — every observation, and every action it
    took — and sends its reply as the action. A vramen model completes a single
    message, so the play so far is that message."""

    def __init__(self, model: CompletionModel) -> None:
        self._model = model
        # The play, in order: every observation, and every action as it was taken.
        self.transcript: list[str] = []

    def play(self, env: StoryPlayer) -> None:
        env.reset()
        description, continuations = env.get_current_scene()
        self.transcript = []
        while continuations:
            numbered = [f"{number}. {continuation}" for number, continuation in enumerate(continuations, start=1)]
            choices = "\n".join(numbered)
            self.transcript.append(f"{description}\n\n{choices}")
            play_so_far = "\n\n".join(self.transcript)
            action_str = self._model.complete(PLAY_INSTRUCTIONS, play_so_far, MAX_NEW_TOKENS)

            action_int = -1
            try:
                action_int = int(action_str)
            except ValueError:
                break
            if not 1 <= action_int <= len(continuations):
                break

            self.transcript.append(f"Chosen: {action_int}")
            env.step(action_int - 1)
            description, continuations = env.get_current_scene()
        self.transcript.append(description)

    def ask(self, question: str) -> str:
        """The model's answer to a question about the story, asked after the play."""
        play = "\n\n".join(self.transcript)
        asked = f"{play}\n\n{question}"
        answer = self._model.complete(ASK_INSTRUCTIONS, asked, MAX_ANSWER_TOKENS)
        return answer

            
