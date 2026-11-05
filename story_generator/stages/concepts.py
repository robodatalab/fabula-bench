"""The story's salient concepts: what the story is about, kept as its salient
concept cells, first in the story. The author is asked first for the concepts of
their choosing; then the model writes every concept the story needs, the
author's and the ones that complement or augment them, each described as what it
is really about and in what light the story shows it. The author reviews the
whole set.

A concept is an idea, not a thing that appears in the story: a general theme the
story is built on, such as motherhood or war, or a story-specific hook, such as
a stranger stranded under the surface of Mars. Every concept gets a plot of its
own, and every plot respects every concept.

The model writes, and the author reviews, every concept as its title on a line
of its own, opened with "### ", followed by its description:

    ### Motherhood
    A mother's care for her child, shown in the light of what it costs her.
"""

from __future__ import annotations

import re
from uuid import uuid4

from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory
from fabula_bench.players.agent_player import CompletionModel
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stage import Stage, StageStep

QUESTION = "Which concepts should the story be about? One a line, an empty line to finish."

GENERATION_INSTRUCTIONS = """You help an author decide what an interactive story is about: its salient concepts, the ideas a reader should come away understanding, though the story never states them.

A concept is either a general theme the story is built on, such as motherhood, war or justice, or a story-specific hook that keeps a reader wanting to learn more, such as a stranger stranded under the surface of Mars. Every concept will get a plot of its own that illustrates it. A character is not a concept, nor is an event, nor a place or a thing that merely appears in the story.

You are given the concepts the author has chosen so far, each under its title, some with a description. Keep every one of them, and add the concepts they call for: ones that complement them, as a brutal father complements motherhood, and ones that augment them, as social help augments motherhood. Choose each from what the others are really about.

Describe every concept as an idea, in one to three sentences: what it is really about, and in what light the story shows it. A general theme is defined the way an encyclopedia defines the idea, narrowed to how this story uses it. A story-specific hook is described by its role in the story: what it is, what drives it, and why a reader wants to learn more. Describe none as a list of events.

When you are also given the author's comment on the concepts you wrote before, answer it.

Write every concept as its title on a line of its own, opened with "### ", followed by its description, and nothing else."""

# Room for the titles and the descriptions of a story's concepts.
MAX_CONCEPTS_TOKENS = 1500


def _read_titles(typed: str) -> list[str]:
    """The titles the author typed, in order, each once."""
    titles: list[str] = []
    for line in typed.splitlines():
        unmarked = line.strip().lstrip("-*• ")
        title = unmarked.strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def _read_concepts(written: str) -> list[tuple[str, str]]:
    """The concepts the model wrote, in order: each one's title and description."""
    _, *blocks = re.split(r"^### ", written, flags=re.MULTILINE)
    concepts: list[tuple[str, str]] = []
    for block in blocks:
        title, _, description = block.partition("\n")
        concept = (title.strip(), description.strip())
        concepts.append(concept)
    return concepts


class AskForConceptsStep(StageStep):
    """The concepts of the author's choosing, asked for first and added to the
    story's concepts, with no description yet."""

    def __call__(self, document: Document, reviews: TerminalReview, reviewer_instruction: str) -> tuple[ReviewResult, Document]:
        typed = reviews.ask(QUESTION)
        titles = _read_titles(typed)
        held = document.salient_concepts()
        held_titles = [concept.title for concept in held]

        chosen = []
        for title in titles:
            if title in held_titles:
                continue
            identifier = uuid4()
            concept_id = str(identifier)
            concept = SalientConceptCell(title=title, references=[], source="", _unique_id=concept_id)
            chosen.append(concept)

        others = [cell for cell in document.cells if not isinstance(cell, SalientConceptCell)]
        document = document.with_cells([*held, *chosen, *others])
        review_result = ReviewResult.success()
        return review_result, document


class GenerateConceptsStep(StageStep):
    """Every concept the story needs: the author's, described, and the ones that
    complement or augment them."""

    def __init__(self, model: CompletionModel) -> None:
        self._model = model

    def __call__(self, document: Document, reviews: TerminalReview, reviewer_instruction: str) -> tuple[ReviewResult, Document]:
        story = InteractiveAuthorStory(document)
        chosen = story.written_concepts()
        asked = f"\n\nThe author asks you to do it again: {reviewer_instruction}" if reviewer_instruction else ""
        request = f"The concepts so far:\n{chosen}{asked}"
        written = self._model.complete(GENERATION_INSTRUCTIONS, request, MAX_CONCEPTS_TOKENS)
        concepts_written = written.strip()

        review_result = reviews(concepts_written)
        if not review_result.is_passed():
            return review_result, document

        # The concepts stand first in the story, in the order written; one the
        # story held keeps its cell, and one left out is gone.
        held_of_title = {concept.title: concept for concept in document.salient_concepts()}
        read = _read_concepts(concepts_written)
        concepts = []
        for title, description in read:
            held = held_of_title.get(title)
            if held is None:
                identifier = uuid4()
                concept_id = str(identifier)
                concept = SalientConceptCell(title=title, references=[], source=description, _unique_id=concept_id)
            else:
                concept = held.with_source(description)
            concepts.append(concept)

        others = [cell for cell in document.cells if not isinstance(cell, SalientConceptCell)]
        document = document.with_cells([*concepts, *others])
        return review_result, document


class Concepts(Stage):

    def __init__(self, model: CompletionModel) -> None:
        self._model = model

    def run(self, document: Document) -> list[StageStep]:
        ask_step = AskForConceptsStep()
        generate_step = GenerateConceptsStep(self._model)
        concepts_steps: list[StageStep] = [ask_step, generate_step]
        return concepts_steps
