"""A stage of writing a story, the review every one of its drafts may go through,
and the author's confidence that decides which drafts do."""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from story_generator.stage_visitor import Review, StageVisitor, Verdict

# How far every draft the author accepts as drafted moves the confidence in its
# kind towards certainty.
RISE = 0.2

# The most confidence there can be in a kind of draft: at least one draft in ten
# is still reviewed, so that a drift in the drafts is caught.
CAP = 0.9


class AuthorStopped(Exception):
    """The author stopped the workflow in the middle of a stage, which is left
    unfinished."""


class Confidence:
    """The author's confidence in every kind of draft, by the kind's name: 0 at
    first, so that every draft is reviewed; rising a fifth of the way towards
    certainty with every draft the author accepts as drafted, and halving with
    every draft the author revises; never above `CAP`. A draft is reviewed by
    chance, the more likely the less the confidence in its kind: a kind of draft
    is written by a prompt of its own, and trust earned by one prompt is not
    trust in another."""

    def __init__(self, levels: dict[str, float], chance: random.Random) -> None:
        self.levels = dict(levels)
        self._chance = chance

    def level(self, kind: str) -> float:
        level = self.levels.get(kind, 0.0)
        return level

    def selects(self, kind: str) -> bool:
        """Whether the author reviews the next draft of the kind."""
        level = self.level(kind)
        drawn = self._chance.random()
        return drawn < 1 - level

    def accepted(self, kind: str) -> None:
        """The author accepted a draft of the kind as it was drafted."""
        level = self.level(kind)
        risen = level + (1 - level) * RISE
        self.levels[kind] = min(risen, CAP)

    def revised(self, kind: str) -> None:
        """The author had a draft of the kind revised."""
        level = self.level(kind)
        self.levels[kind] = level / 2


class Stage(ABC):
    """One stage of writing a story. It reads the story, and has the author review
    what it makes of it through the renderer, which visits the stage. A stage that
    adds to the story drafts, item by item, what it adds, has the author review
    the drafts the confidence selects, and writes into the story what the author
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
        story's .author file, `renderer`, the StageVisitor that shows the author
        its drafts, `confidence`, the Confidence that decides which drafts the
        author reviews, and `checkpoint`, which the stage calls right after every
        time it writes the story, so that the confidence stands checkpointed with
        what it wrote. Raises AuthorStopped when the author stops."""

    @abstractmethod
    def accept(self, visitor: StageVisitor) -> Review:
        """Has the visitor show the stage's draft, and returns the author's review
        of it."""


def reviewed(
    stage: Stage,
    visitor: StageVisitor,
    revise: Callable[[list[str]], str],
    confidence: Confidence,
    kind: str | None,
) -> str:
    """The stage's draft as the author accepts it: shown through the visitor, and
    revised by `revise`, given every comment the author has made on it so far,
    until the author accepts it. A draft of a kind is shown only when the
    confidence in its kind selects it, and is accepted unseen, and logged, when it
    does not; a draft of no kind is always shown. Raises AuthorStopped when the
    author stops."""
    logger = logging.getLogger(__name__)
    if kind is not None and not confidence.selects(kind):
        level = confidence.level(kind)
        logger.info("a draft of %s was accepted unreviewed, at confidence %.2f", kind, level)
        return stage.draft
    comments: list[str] = []
    review = stage.accept(visitor)
    while review.verdict is Verdict.REVISE:
        comments.append(review.comment)
        stage.draft = revise(comments)
        review = stage.accept(visitor)
    if review.verdict is Verdict.STOP:
        raise AuthorStopped
    if kind is not None:
        if comments:
            confidence.revised(kind)
        else:
            confidence.accepted(kind)
        level = confidence.level(kind)
        logger.info("confidence in %s: %.2f", kind, level)
    return stage.draft
