"""Writes a story with its author, stage by stage, in a terminal.

Run as `python -m story_generator`, with the Anthropic API key in the
environment; it asks for the story's .author file, and creates it if there is
none. Stopped in a stage, run it again on the same file to resume at that stage.
`--back-to "<stage>"` goes back to a stage, and runs it, and every stage that
depends on it, again.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from fabula_bench.models.claude_model import ClaudeModel
from story_generator.visitors.terminal_renderer import TerminalRenderer
from story_generator.workflow import Workflow

WRITING_MODEL = "claude-opus-5-5"


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a story with its author, stage by stage.")
    parser.add_argument("--back-to", help="the stage to go back to")
    arguments = parser.parse_args()

    answer = input("The story's .author file, to create or to resume: ")
    name = answer.strip()
    story = Path(name)
    # A new story starts as an empty file.
    if not story.exists():
        story.write_text("", encoding="utf-8")
    model = ClaudeModel(WRITING_MODEL)
    renderer = TerminalRenderer()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("   [%(stage)s] %(message)s")
    handler.setFormatter(formatter)
    workflow = Workflow(story, model, renderer, handler)
    finished = workflow.finished()
    for name in workflow.stages:
        mark = "x" if name in finished else " "
        print(f"[{mark}] {name}")
    workflow.run(arguments.back_to)


if __name__ == "__main__":
    main()
