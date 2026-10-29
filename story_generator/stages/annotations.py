"""Every salient concept annotated on the finished scenes, drafted by the model:
the passages that show the concept's idea, never one that merely names it.

The author reviews the passages themselves; the model writes them, and is shown
its draft, one passage a line, by the label of its scene, the words it starts
with and the words it ends with, each copied from the scene:

    S12 | She was silent for a moment | sat without speaking
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from authordoc.cells.cell import Cell
from authordoc.cells.salient_concept_cell import SalientConceptReference
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import Stage, reviewed
from story_generator.stage_visitor import Review, StageVisitor
from story_generator.stages.scenes import get_cell_of_event, get_scene_prose

INSTRUCTIONS = """You annotate one salient concept of an interactive story on the story's scenes: you find the passages that show the concept's idea.

A passage shows the idea; for a character, it is behaviour that reveals who they are or what drives them. A passage that merely names the concept, or mentions what it is about, does not show it. A passage can be part of a sentence, and can run over several.

You are given the concept and the story's scenes, each headed by its label, as in S12. Write one passage a line, as: the scene's label | the words the passage starts with | the words it ends with. Copy both exactly from the scene, the first long enough to find the passage by, the second where it ends.

When you are also given your draft and the author's comments on it, rewrite the draft to answer every comment, and change nothing the comments do not ask you to change.

Write the lines and nothing else."""

# Room for the passages of one concept.
MAX_PASSAGES_TOKENS = 2000

# How many words a passage the story holds is quoted by, at its start and at its end.
QUOTED_WORDS = 6


def get_scene_cells(document: Document) -> list[Cell]:
    """The cells that tell the story's scenes, in the order they come in; the
    scene in the n-th of them is labelled Sn."""
    cell_of_event = get_cell_of_event(document)
    telling = set(cell_of_event.values())
    cells = [cell for cell in document.cells if cell.unique_id in telling]
    return cells


def read_passages(document: Document, scene_cells: list[Cell], written: str) -> list[StoryWordRange]:
    """The story words of every passage the draft lists that is found in its
    scene; a line naming no scene, or quoting words not in it, is left out."""
    cell_of_label = {f"S{number}": cell for number, cell in enumerate(scene_cells, start=1)}
    words = list(StoryWordsIterator(document))
    passages = []
    for line in written.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        label, opening, closing = [part.strip() for part in parts]
        cell = cell_of_label.get(label)
        if cell is None or not opening or not closing:
            continue
        start = cell.source.find(opening)
        if start < 0:
            continue
        closing_at = cell.source.find(closing, start)
        if closing_at < 0:
            continue
        end = closing_at + len(closing)
        numbers = [
            word.number
            for word in words
            if word.cell_id == cell.unique_id
            and word.end_character_offset_in_cell > start
            and word.start_character_offset_in_cell < end
        ]
        if numbers:
            passage = StoryWordRange(numbers[0], numbers[-1])
            passages.append(passage)
    return passages


def written_passages(document: Document, scene_cells: list[Cell], references: list[SalientConceptReference]) -> str:
    """A concept's passages as a draft lists them, each quoted by its first and
    its last words, exactly as they stand in its scene."""
    label_of_cell = {cell.unique_id: f"S{number}" for number, cell in enumerate(scene_cells, start=1)}
    words = list(StoryWordsIterator(document))
    lines = []
    for reference in references:
        covered = [
            word
            for word in words
            if reference.story_word_range.first_word <= word.number <= reference.story_word_range.last_word
        ]
        if not covered or covered[0].cell_id not in label_of_cell:
            continue
        cell = next(cell for cell in scene_cells if cell.unique_id == covered[0].cell_id)
        first_words = covered[:QUOTED_WORDS]
        last_words = covered[-QUOTED_WORDS:]
        opening = cell.source[first_words[0].start_character_offset_in_cell : first_words[-1].end_character_offset_in_cell]
        closing = cell.source[last_words[0].start_character_offset_in_cell : last_words[-1].end_character_offset_in_cell]
        label = label_of_cell[cell.unique_id]
        lines.append(f"{label} | {opening} | {closing}")
    written = "\n".join(lines)
    return written


class Annotations(Stage):
    def __init__(self, model: CompletionModel) -> None:
        super().__init__()
        self._model = model
        # What the renderer shows: the concept, and the passages the draft
        # finds for it.
        self.concept = ""
        self.description = ""
        self.passages: list[str] = []

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        scene_cells = get_scene_cells(document)
        concepts_at_the_start = document.salient_concepts()
        count = len(concepts_at_the_start)
        for index in range(count):
            concepts = document.salient_concepts()
            concept = concepts[index]
            self.concept = concept.title
            self.description = concept.source
            self.progress = (index, count)
            held = written_passages(document, scene_cells, concept.references)
            self.draft = held if held else self._drafted(scene_cells, [])
            self.passages = self._found(document, scene_cells, self.draft)

            def revised(comments: list[str]) -> str:
                passages = self._drafted(scene_cells, comments)
                self.passages = self._found(document, scene_cells, passages)
                return passages

            accepted = reviewed(self, renderer, revised)
            found = read_passages(document, scene_cells, accepted)
            references = []
            for words in found:
                identifier = uuid4()
                reference_id = str(identifier)
                reference = SalientConceptReference(reference_id, words)
                references.append(reference)
            annotated = replace(concept, references=references)
            cells = [annotated if cell.unique_id == concept.unique_id else cell for cell in document.cells]
            document = Document.from_cells(cells, document.path)
            story.write_text(document.text, encoding="utf-8")
            self.progress = (index + 1, count)
            logger.info("concept %d of %d annotated", index + 1, count, extra={"progress": self.progress})

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_annotations(self)
        return review

    def _found(self, document: Document, scene_cells: list[Cell], passages: str) -> list[str]:
        """The text of every passage a draft lists that is found in its scene."""
        found = read_passages(document, scene_cells, passages)
        story_words = StoryWordsIterator(document)
        texts = [story_words.text(words) for words in found]
        return texts

    def _drafted(self, scene_cells: list[Cell], comments: list[str]) -> str:
        """The concept's passages, drafted afresh, or, given the author's comments,
        the draft under review revised to answer them."""
        scenes = []
        for number, cell in enumerate(scene_cells, start=1):
            prose = get_scene_prose(cell.source)
            scenes.append(f"S{number}:\n{prose}")
        written_scenes = "\n\n".join(scenes)
        request = f"The concept, {self.concept}:\n{self.description}\n\nThe story's scenes:\n\n{written_scenes}"
        if comments:
            written_comments = "\n".join(f"- {comment}" for comment in comments)
            request = f"{request}\n\nYour draft:\n{self.draft}\n\nThe author's comments, oldest first:\n{written_comments}"
        written = self._model.complete(INSTRUCTIONS, request, MAX_PASSAGES_TOKENS)
        passages = written.strip()
        return passages
