"""The author's ideas for the story's plots, one per paragraph, each a premise in
the author's own words, kept in a note at the start of the story. Nothing is
drafted for the author here: whatever the author adds is an idea, and accepting
ends the list."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from authordoc.cells.note_cell import NoteCell
from authordoc.storydoc import Document
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor

HEADING = "## Plot ideas"

# The note the ideas are kept in has the same id in every story, so that this
# stage, and the next, find it.
_IDEAS_NOTE_UUID = uuid5(NAMESPACE_URL, "fabula-bench/plot ideas")
IDEAS_NOTE_ID = str(_IDEAS_NOTE_UUID)


def get_ideas(document: Document) -> list[str]:
    """The author's plot ideas the story keeps, in order."""
    note = document.cell_with_id(IDEAS_NOTE_ID)
    if note is None:
        return []
    _, _, written = note.source.partition(f"{HEADING}\n\n")
    paragraphs = written.split("\n\n")
    ideas = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
    return ideas


class PlotIdeas(Stage):
    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        held = get_ideas(document)
        self.draft = "\n\n".join(held)

        def added(comments: list[str]) -> str:
            idea = comments[-1].strip()
            if not self.draft:
                return idea
            ideas = f"{self.draft}\n\n{idea}"
            return ideas

        accepted = reviewed(self, renderer, added)
        note = NoteCell(source=f"{HEADING}\n\n{accepted}", _unique_id=IDEAS_NOTE_ID)
        other_cells = [cell for cell in document.cells if cell.unique_id != IDEAS_NOTE_ID]
        with_the_ideas = Document.from_cells([note, *other_cells], document.path)
        story.write_text(with_the_ideas.text, encoding="utf-8")
        ideas = get_ideas(with_the_ideas)
        count = len(ideas)
        self.progress = (count, count)
        logger.info("%d plot ideas", count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_plot_ideas(self)
        return review
