"""Playing an environment from the terminal."""

from __future__ import annotations

from fabula_bench.story_player.story_player import StoryPlayer


class HumanPlayer:
    """Prints each observation, and sends what is typed as the action."""

    def play(self, env: StoryPlayer) -> None:
        env.reset()
        description, continuations = env.get_current_scene()
        while continuations:
            print(description)
            for number, continuation in enumerate(continuations, start=1):
                print(f"  {number}: {continuation}")
            action = int(input("Choice> ")) - 1
            print("\n\n----------------\n")
            env.step(action)
            description, continuations = env.get_current_scene()
        print(description)
