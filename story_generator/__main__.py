"""Writes the story of an `.author` file's plots into the file.

Run as `python -m story_generator path/to/story.author`.
"""

import sys
from pathlib import Path

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.storydoc.storydoc import Document
from story_generator.scene_writer import SceneWriter
from story_generator.story import with_the_story

WRITING_MODEL = "claude-opus-5-5"


def main() -> None:
    path = Path(sys.argv[1])
    document = Document.load(path)
    model = ClaudeModel(WRITING_MODEL)
    scene_writer = SceneWriter(model)

    def tell(written: int, scenes: int) -> None:
        print(f"scene {written} of {scenes} written", flush=True)

    story = with_the_story(document, scene_writer, tell)
    path.write_text(story.text, encoding="utf-8")
    print(f"the story is in {path}")


if __name__ == "__main__":
    main()
