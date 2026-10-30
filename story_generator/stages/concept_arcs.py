"""How each concept a plot illustrates shows along the plot, event by event,
drafted by the model and kept in a note after the plot. A concept does not show
equally at every event: a general theme may show at nearly every one; another
is absent at first, surfaces at one event, and grows from there. The scenes are
written from these arcs: an event gets a version for a concept only where the
concept shows, and as its arc says it shows there.

The author reviews, and the model writes, a plot's arcs as every event's moment
and what happens, and under it, for every concept the plot illustrates, how the
concept shows there, or a dash where it does not:

    0.1 The politician meets Captain Varn, and starts pretending to like her.
      Classical romance: —
      Good beats evil: the evil side: he courts her only for what she can tell him.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from authordoc.cells.note_cell import NoteCell
from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Confidence, Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.concepts import written_concepts
from story_generator.stages.plot_ends import get_illustrated

INSTRUCTIONS = """You help an author plan how the salient concepts a plot illustrates show along the plot, event by event, before its scenes are written. A concept does not show equally at every event: a general theme may show at nearly every one; another is absent at first, surfaces at one event, and grows from there; another shows only where the plot turns. Told event by event, the plot carries each concept from where it starts to where it leads.

You are given the story's concepts, the concepts the plot illustrates, and the plot's events, in order, each followed by the plot's concepts. For every event and every concept, write in a sentence how the concept shows at that event: who shows it, and how, at this point of the plot. Where it does not show at that event, write —. Make no concept show where nothing in the event carries it.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write in exactly the form you are given: every event's line as it is, and under it, for every concept, a line indented by two spaces: the concept's title, a colon, and how the concept shows, or —. Write nothing else."""

# Room for the arcs of one plot's concepts.
MAX_ARCS_TOKENS = 4000

# Heads the note a plot's arcs are kept in, before the plot's title.
HEADING = "## Concept arcs of "

# Stands for a concept that does not show at an event.
ABSENT = "—"


def get_arcs_note_id(plot: PlotCell) -> str:
    """The id of the note the plot's arcs are kept in: the same for the plot
    every time, so that every stage finds it."""
    arcs_uuid = uuid5(NAMESPACE_URL, f"fabula-bench/concept arcs/{plot.unique_id}")
    note_id = str(arcs_uuid)
    return note_id


def written_arcs(events: Sequence[PlotNode], titles: Sequence[str], arcs: Sequence[dict[str, str]]) -> str:
    """The arcs of a plot's concepts as a draft lists them."""
    blocks = []
    for event, shows in zip(events, arcs):
        lines = [f"{event.timestamp} {event.summary}"]
        for title in titles:
            how = shows.get(title) or ABSENT
            lines.append(f"  {title}: {how}")
        block = "\n".join(lines)
        blocks.append(block)
    written = "\n".join(blocks)
    return written


def read_arcs(written: str, events: Sequence[PlotNode], titles: Sequence[str]) -> list[dict[str, str]]:
    """How every concept shows at every event of the plot, as the draft lists it:
    for each event, in order, the concepts that show there, with how; a line
    naming no concept of the plot is left out, and logged."""
    logger = logging.getLogger(__name__)
    arcs: list[dict[str, str]] = []
    for line in written.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            arcs.append({})
            continue
        if not arcs:
            continue
        written_title, _, how = line.partition(":")
        title = written_title.strip()
        shows = how.strip()
        if title not in titles:
            logger.warning("%s is no concept of the plot; its arc is left out", title)
            continue
        if shows and shows not in (ABSENT, "-", "–"):
            arcs[-1][title] = shows
    listed_count = len(arcs)
    event_count = len(events)
    if listed_count != event_count:
        logger.warning("the arcs list %d events, and the plot has %d", listed_count, event_count)
    missing = event_count - listed_count
    padded = [*arcs, *({} for _ in range(missing))]
    kept = padded[:event_count]
    return kept


def get_arcs(document: Document, plot: PlotCell) -> list[dict[str, str]] | None:
    """How every concept of the plot shows at every event, as the story keeps it;
    None when the story keeps no arcs for the plot, or keeps them for other events
    or concepts than the plot has now."""
    note_id = get_arcs_note_id(plot)
    note = document.cell_with_id(note_id)
    if note is None:
        return None
    _, _, written = note.source.partition("\n\n")
    lines = written.splitlines()
    blocks = [line for line in lines if line.strip() and not line.startswith(" ")]
    listed: set[str] = set()
    for line in lines:
        if line.startswith(" "):
            written_title, _, _ = line.partition(":")
            title = written_title.strip()
            listed.add(title)
    titles = get_illustrated(plot)
    if len(blocks) != len(plot.nodes) or listed != set(titles):
        return None
    arcs = read_arcs(written, plot.nodes, titles)
    return arcs


class ConceptArcs(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows beside the arcs: the plot, and the concepts it
        # illustrates, each with its description.
        self.plot = ""
        self.description = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        confidence: Confidence = params["confidence"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots_at_the_start = document.plots()
        count = len(plots_at_the_start)
        for index in range(count):
            plots = document.plots()
            plot = plots[index]
            titles = get_illustrated(plot)
            concepts = document.salient_concepts()
            descriptions = [f"{concept.title}: {concept.source}" for concept in concepts if concept.title in titles]
            self.plot = plot.title
            self.description = "\n".join(descriptions)
            self.progress = (index, count)
            if not titles:
                logger.warning("%s illustrates no concept, so it has no arcs", plot.title)
                continue
            held = get_arcs(document, plot)
            self.draft = written_arcs(plot.nodes, titles, held) if held is not None else self._drafted(document, plot, [])

            def revised(comments: list[str]) -> str:
                arcs = self._drafted(document, plot, comments)
                return arcs

            accepted = reviewed(self, renderer, revised, confidence, "concept arcs")
            note_id = get_arcs_note_id(plot)
            note = NoteCell(source=f"{HEADING}{plot.title}\n\n{accepted}", _unique_id=note_id)
            if document.cell_with_id(note_id) is not None:
                cells = [note if cell.unique_id == note_id else cell for cell in document.cells]
            else:
                plot_at = next(at for at, cell in enumerate(document.cells) if cell.unique_id == plot.unique_id)
                after_the_plot = plot_at + 1
                cells = [*document.cells[:after_the_plot], note, *document.cells[after_the_plot:]]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("arcs of plot %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_concept_arcs(self)
        return review

    def _drafted(self, document: Document, plot: PlotCell, comments: list[str]) -> str:
        """The plot's arcs, drafted afresh, or, given the author's comments, the
        draft under review revised to answer them; written again as the plot's
        events and concepts are."""
        titles = get_illustrated(plot)
        concepts = document.salient_concepts()
        written_story_concepts = written_concepts(concepts)
        empty = [{} for _ in plot.nodes]
        to_fill = written_arcs(plot.nodes, titles, empty)
        request = (
            f"The story's concepts:\n{written_story_concepts}\n\n"
            f"The concepts the plot, {plot.title}, illustrates:\n{self.description}\n\n"
            f"The plot's events, each followed by its concepts:\n{to_fill}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_ARCS_TOKENS)
        arcs = read_arcs(written, plot.nodes, titles)
        drafted = written_arcs(plot.nodes, titles, arcs)
        return drafted
