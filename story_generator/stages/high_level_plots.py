"""A high-level plot for each of the author's plot ideas, drafted by the model and
kept as a note: the plot's title, what it is about, and about four numbered
points, one for each act of the world's clock it spans."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from authordoc.cells.note_cell import NoteCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.plot_ideas import IDEAS_NOTE_ID, get_ideas

INSTRUCTIONS = """You help an author write an interactive story in which many plots, each a full story of its own, mesh in one world.

You are given the author's idea for a new plot, the outlines of the plots the world already holds, and the acts of the world's clock. Write the new plot's high-level outline: its title, one sentence saying what the plot is about, and about four numbered points, one for each act it spans, each a plain statement of what happens and why. Keep to the author's idea, and add no characters, places or events that neither the idea nor the world calls for.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write the outline in exactly this form, and nothing else:

## <the plot's title>

<one sentence saying what the plot is about>

1. <what happens in the first act the plot spans, and why>
2. <...>"""

# Room for an outline of a few points.
MAX_OUTLINE_TOKENS = 1000

# The acts of a world whose clock has no events on it yet.
FIRST_ACTS = ["1", "2", "3", "4"]


def get_outlines(document: Document) -> list[NoteCell]:
    """The notes that outline the story's plots: every note but the author's
    ideas, in order."""
    outlines = [cell for cell in document.cells if isinstance(cell, NoteCell) and cell.unique_id != IDEAS_NOTE_ID]
    return outlines


def get_outline_title(outline: str) -> str:
    """The title an outline gives its plot: its heading, without the hashes."""
    heading, _, _ = outline.partition("\n")
    title = heading.lstrip("# ").strip()
    return title


def get_outline_overview(outline: str) -> str:
    """What an outline says its plot is about: the paragraph after its heading."""
    paragraphs = outline.split("\n\n")
    overview = paragraphs[1].strip() if len(paragraphs) > 1 else ""
    return overview


def get_acts(document: Document) -> list[str]:
    """The acts the world's clock has events in: the first number of their
    moments, in order."""
    acts = {event.timestamp.split(".")[0] for plot in document.plots() for event in plot.nodes if event.timestamp}
    if not acts:
        return FIRST_ACTS
    ordered = sorted(acts, key=int)
    return ordered


class HighLevelPlots(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # The idea under review, for the renderer to show.
        self.idea = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        ideas = get_ideas(document)
        count = len(ideas)
        for index, idea in enumerate(ideas):
            self.idea = idea
            self.progress = (index, count)
            # The outline's note has an id made from its idea, so that the stage
            # finds it again.
            identifier = uuid5(NAMESPACE_URL, f"fabula-bench/outline/{idea}")
            outline_id = str(identifier)
            held = document.cell_with_id(outline_id)
            self.draft = held.source if held is not None else self._drafted(document, outline_id, [])

            def revised(comments: list[str]) -> str:
                outline = self._drafted(document, outline_id, comments)
                return outline

            accepted = reviewed(self, renderer, revised)
            note = NoteCell(source=accepted, _unique_id=outline_id)
            if held is not None:
                cells = [note if cell.unique_id == outline_id else cell for cell in document.cells]
            else:
                notes_at = [at for at, cell in enumerate(document.cells) if isinstance(cell, NoteCell)]
                after_the_notes = notes_at[-1] + 1 if notes_at else 0
                cells = [*document.cells[:after_the_notes], note, *document.cells[after_the_notes:]]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("outline %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_high_level_plots(self)
        return review

    def _drafted(self, document: Document, outline_id: str, comments: list[str]) -> str:
        """The idea's outline, drafted afresh, or, given the author's comments, the
        draft under review revised to answer them."""
        outlines = get_outlines(document)
        world = [outline.source for outline in outlines if outline.unique_id != outline_id]
        written_world = "\n\n".join(world) or "None yet."
        acts = get_acts(document)
        written_acts = ", ".join(acts)
        request = (
            f"The author's idea:\n{self.idea}\n\n"
            f"The world's plots so far:\n{written_world}\n\n"
            f"The acts of the world's clock: {written_acts}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_OUTLINE_TOKENS)
        outline = written.strip()
        return outline
