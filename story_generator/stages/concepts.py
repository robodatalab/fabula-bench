"""The salient concepts each plot pursues, drafted by the model and kept as the
story's salient concept cells. General concepts are the themes a plot is built
on, defined as an encyclopedia defines the idea, narrowed to the story;
story-specific concepts are what a plot builds up to, which keep a reader
wanting to learn more. A concept two plots pursue is one concept, under one
title.

The author reviews, and the model writes, a plot's concepts as:

    ## General

    ### <title>
    <definition>

    ## Story-specific

    ### <title>
    <description>
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.plot_cell import PlotCell
from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.high_level_plots import get_outline_title, get_outlines
from story_generator.stages.low_level_plots import written_events

INSTRUCTIONS = """You help an author name the salient concepts one plot of an interactive story pursues: the ideas a reader should come away understanding, though the story never states them.

There are two kinds.

General concepts are the themes the plot is built on, such as motherhood, war or justice. Define each the way an encyclopedia defines the idea, narrowed to how this story uses it, in one to three sentences.

Story-specific concepts are what the plot builds up to: what keeps a reader pinned to the story and wanting to learn more. A plot can build up to several, and not only at its end: an intermediate concept can keep the reader hooked. Each is built over several events. Name each by its role in the story, and describe it as an idea, not as a list of events. A character is not a story-specific concept, nor is an event that happens once and leads nowhere, nor anything a general concept already covers.

You are given the plot's outline and events, and the concepts the world already has. Where the plot pursues one of them, write it with its title and description unchanged.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write in exactly this form, and nothing else:

## General

### <title>
<definition>

## Story-specific

### <title>
<description>"""

# Room for the concepts of one plot.
MAX_CONCEPTS_TOKENS = 2000


def read_concepts(written: str) -> list[tuple[str, str]]:
    """The concepts a draft lists, as their titles and descriptions, in order."""
    concepts = []
    # A concept's heading may open the draft, with no line before it.
    sections = f"\n{written}".split("\n### ")
    for section in sections[1:]:
        title, _, rest = section.partition("\n")
        description, _, _ = rest.partition("\n## ")
        concepts.append((title.strip(), description.strip()))
    return concepts


class Concepts(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # The plot under review, for the renderer to show.
        self.title = ""

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots = document.plots()
        count = len(plots)
        for index, plot in enumerate(plots):
            self.title = plot.title
            self.progress = (index, count)
            self.draft = self._drafted(document, plot, [])

            def revised(comments: list[str]) -> str:
                concepts = self._drafted(document, plot, comments)
                return concepts

            accepted = reviewed(self, renderer, revised)
            concepts = read_concepts(accepted)
            cells = list(document.cells)
            for title, description in concepts:
                held_at = next(
                    (at for at, cell in enumerate(cells) if isinstance(cell, SalientConceptCell) and cell.title == title),
                    None,
                )
                if held_at is not None:
                    held = cells[held_at]
                    described = replace(held, source=description)
                    cells[held_at] = described
                    continue
                concepts_at = [at for at, cell in enumerate(cells) if isinstance(cell, SalientConceptCell)]
                after_them = concepts_at[-1] + 1 if concepts_at else len(cells)
                identifier = uuid4()
                concept_id = str(identifier)
                concept = SalientConceptCell(title=title, references=[], source=description, _unique_id=concept_id)
                cells.insert(after_them, concept)
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("concepts of plot %d of %d accepted", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_concepts(self)
        return review

    def _drafted(self, document: Document, plot: PlotCell, comments: list[str]) -> str:
        """The plot's concepts, drafted afresh, or, given the author's comments, the
        draft under review revised to answer them."""
        outlines = get_outlines(document)
        outline = next((note.source for note in outlines if get_outline_title(note.source) == plot.title), plot.overview)
        events = written_events(plot.nodes)
        held = [f"### {concept.title}\n{concept.source}" for concept in document.salient_concepts()]
        world_concepts = "\n\n".join(held) or "None yet."
        request = (
            f"The plot's outline:\n{outline}\n\n"
            f"The plot's events:\n{events}\n\n"
            f"The concepts the world already has:\n{world_concepts}"
        )
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_CONCEPTS_TOKENS)
        concepts = written.strip()
        return concepts
