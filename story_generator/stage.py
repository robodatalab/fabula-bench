"""A stage of writing a story, and the review every one of its drafts goes
through."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from story_generator.stage_visitor import Review, StageVisitor, Verdict


class AuthorStopped(Exception):
    """The author stopped the workflow in the middle of a stage, which is left
    unfinished."""


class Stage(ABC):
    """One stage of writing a story. It reads the story, drafts, item by item,
    what the stage adds to it, has the author review every draft through the
    renderer, which visits the stage, and writes into the story what the author
    accepts. It logs its progress through a logger it makes where it works, with
    `extra={"progress": (done, total)}`."""

    def __init__(self) -> None:
        # What a renderer shows of every stage: the draft under review, and how
        # many of the stage's items the author has accepted, of how many.
        self.draft = ""
        self.progress = (0, 0)

    @abstractmethod
    def run(self, **params: Any) -> None:
        """Does the stage's work. The workflow gives it `story`, the path to the
        story's .author file, and `renderer`, the StageVisitor that shows the
        author its drafts. Raises AuthorStopped when the author stops."""

    @abstractmethod
    def accept(self, visitor: StageVisitor) -> Review:
        """Has the visitor show the stage's draft, and returns the author's review
        of it."""


def reviewed(stage: Stage, visitor: StageVisitor, revise: Callable[[list[str]], str]) -> str:
    """The stage's draft as the author accepts it: shown through the visitor, and
    revised by `revise`, given every comment the author has made on it so far,
    until the author accepts it. Raises AuthorStopped when the author stops."""
    comments: list[str] = []
    review = stage.accept(visitor)
    while review.verdict is Verdict.REVISE:
        comments.append(review.comment)
        stage.draft = revise(comments)
        review = stage.accept(visitor)
    if review.verdict is Verdict.STOP:
        raise AuthorStopped
    return stage.draft
