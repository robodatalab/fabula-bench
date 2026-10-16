"""Running the benchmark: every story asked of a model, every reply returned.

Only the salient-information task runs so far. The plot task needs plots to be
annotated in `.author` files, and the format does not say how yet. Scoring is
not written either, so a run returns the model's replies as they are.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fabula_bench import storydoc
from fabula_bench.models.base import Model, Turn

SALIENT_INFORMATION = "salient-information"

SALIENT_INFORMATION_PROMPT = """<story>
{story}
</story>

Identify the salient information in the story above: the salient concepts it is \
built around, including any it never states outright. List each salient concept \
with a short title and a sentence saying what it is in this story."""


@dataclass(frozen=True)
class Answer:
    """A model's reply to one task about one story."""

    story: Path
    task: str
    reply: str


def evaluate(model: Model, stories: Path) -> list[Answer]:
    """Ask `model` about every story under `stories`, a directory of `.author`
    files. A story is asked about its salient information when it has
    salient concepts annotated, since only then can the reply be scored."""
    found = stories.rglob(f"*{storydoc.EXTENSION}")
    story_paths = sorted(found)
    documents = [storydoc.Document.load(path) for path in story_paths]
    stories_with_documents = zip(story_paths, documents)
    annotated = [
        (path, document)
        for path, document in stories_with_documents
        if document.salient_concepts()
    ]
    conversations = [_salient_information_conversation(document) for _, document in annotated]
    replies = model.generate(conversations)
    replies_to_stories = zip(annotated, replies, strict=True)
    answers = [
        Answer(path, SALIENT_INFORMATION, reply) for (path, _), reply in replies_to_stories
    ]
    return answers


def _salient_information_conversation(document: storydoc.Document) -> list[Turn]:
    # The story as a reader of the book sees it: its prose, without the
    # annotations, which live in cells of their own.
    markdown_cells = document.markdown_cells()
    prose_of_each_cell = [cell.source for cell in markdown_cells]
    prose = "\n\n".join(prose_of_each_cell)
    asked = SALIENT_INFORMATION_PROMPT.format(story=prose)
    user_turn = Turn("user", asked)
    conversation = [user_turn]
    return conversation
