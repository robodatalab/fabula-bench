"""The story's salient concepts: what the story is about, kept as its salient
concept cells, first in the story. The author says what the story is about, and
the model keeps the list of the concepts' titles; then the model describes each
concept, and the author reviews every description.

A concept is an idea, not a thing that appears in the story: a general theme the
story is built on, such as motherhood or war, or a story-specific hook, such as
a stranger stranded under the surface of Mars. Every concept gets a plot of its
own, and every plot respects every concept.

The author reviews, and the model writes, the list as one title a line.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor

LIST_INSTRUCTIONS = """You help an author decide what an interactive story is about: its salient concepts, the ideas a reader should come away understanding, though the story never states them.

A concept is either a general theme the story is built on, such as motherhood, war or justice, or a story-specific hook that keeps a reader wanting to learn more, such as a stranger stranded under the surface of Mars. Every concept will get a plot of its own that illustrates it. A character is not a concept, nor is an event, nor a place or a thing that merely appears in the story.

You are given the titles of the concepts so far, one a line, and the author's comments on them. Rewrite the list to answer every comment, and change nothing the comments do not ask you to change.

Write the titles, one a line, and nothing else."""

DESCRIPTION_INSTRUCTIONS = """You help an author describe one salient concept of an interactive story: an idea a reader should come away understanding, though the story never states it. Every concept gets a plot of its own that illustrates it, and every plot respects every concept, so the description is what the plots will be written to show.

Describe the concept as an idea, in one to three sentences. A general theme, such as motherhood or war, is defined the way an encyclopedia defines the idea, narrowed to how this story uses it. A story-specific hook is described by its role in the story: what it is, what drives it, and why a reader wants to learn more. Describe neither as a list of events.

You are given the titles of the story's concepts, what the author has said the story is about, and the concept to describe.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write the description and nothing else."""

# Room for the titles of a story's concepts.
MAX_LIST_TOKENS = 500

# Room for the description of one concept.
MAX_DESCRIPTION_TOKENS = 500


def read_titles(written: str) -> list[str]:
    """The titles a list holds, in order, each once."""
    titles: list[str] = []
    for line in written.splitlines():
        unmarked = line.strip().lstrip("-*• ")
        title = unmarked.strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def written_concepts(concepts: Sequence[SalientConceptCell]) -> str:
    """The concepts, each under its title, with its description."""
    described = [f"### {concept.title}\n{concept.source}" for concept in concepts]
    written = "\n\n".join(described) or "None yet."
    return written


class Concepts(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows: the concept whose description is under
        # review, none while the list is.
        self.concept = ""
        # What the author has said the story is about, in the comments on the
        # list.
        self._about: list[str] = []

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        held = document.salient_concepts()
        held_titles = [concept.title for concept in held]
        self.concept = ""
        self.draft = "\n".join(held_titles)

        def listed(comments: list[str]) -> str:
            self._about = list(comments)
            titles = self._listed(comments)
            return titles

        accepted_list = reviewed(self, renderer, listed)
        titles = read_titles(accepted_list)
        # The concepts stand first in the story, in the list's order; a concept
        # taken off the list is gone, and one added waits for its description.
        held_of_title = {concept.title: concept for concept in held}
        listed_concepts = []
        for title in titles:
            concept = held_of_title.get(title)
            if concept is None:
                identifier = uuid4()
                concept_id = str(identifier)
                concept = SalientConceptCell(title=title, references=[], source="", _unique_id=concept_id)
            listed_concepts.append(concept)
        other_cells = [cell for cell in document.cells if not isinstance(cell, SalientConceptCell)]
        document = Document.from_cells([*listed_concepts, *other_cells], document.path)
        story.write_text(document.text, encoding="utf-8")
        count = len(titles)
        logger.info("%d concepts listed", count, extra={"progress": (0, count)})
        for index, title in enumerate(titles):
            concepts = document.salient_concepts()
            concept = next(concept for concept in concepts if concept.title == title)
            self.concept = title
            self.progress = (index, count)
            self.draft = concept.source if concept.source else self._described(titles, [])

            def revised(comments: list[str]) -> str:
                description = self._described(titles, comments)
                return description

            accepted = reviewed(self, renderer, revised)
            described = replace(concept, source=accepted)
            cells = [described if cell.unique_id == concept.unique_id else cell for cell in document.cells]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("concept %d of %d described", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_concepts(self)
        return review

    def _listed(self, comments: list[str]) -> str:
        """The list under review, revised to answer the author's comments."""
        titles = self.draft or "None yet."
        written_comments = "\n".join(f"- {comment}" for comment in comments)
        request = f"The titles so far:\n{titles}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(LIST_INSTRUCTIONS, request, MAX_LIST_TOKENS)
        listed = written.strip()
        return listed

    def _described(self, titles: list[str], comments: list[str]) -> str:
        """The concept's description, drafted afresh, or, given the author's
        comments, the draft under review revised to answer them."""
        written_titles = "\n".join(f"- {title}" for title in titles)
        request = f"The story's concepts:\n{written_titles}"
        if self._about:
            about = "\n".join(f"- {said}" for said in self._about)
            request = f"{request}\n\nWhat the author has said the story is about:\n{about}"
        request = f"{request}\n\nThe concept to describe: {self.concept}"
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(DESCRIPTION_INSTRUCTIONS, request, MAX_DESCRIPTION_TOKENS)
        description = written.strip()
        return description
