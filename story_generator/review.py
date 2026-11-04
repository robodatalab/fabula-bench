"""The author's review of what the stages' steps produce: shown to the author by
chance, the less often the more the author trusts the stage, and answered with a
pass, or with a fail that says how to do it again."""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

# How far every result the author approves moves the confidence in the stage
# towards certainty.
RISE = 0.2

# The most confidence there can be in a stage: at least one result in ten is
# still reviewed, so that a drift in the results is caught.
CAP = 0.9


class Verdict(Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    STOP = "stop"


@dataclass(frozen=True)
class ReviewResult:
    """The author's answer to a result; when it is to be done again, the comment
    says how."""

    verdict: Verdict
    comment: str = ""

    @classmethod
    def success(cls) -> ReviewResult:
        return cls(Verdict.ACCEPT, "")

    @classmethod
    def failed(cls, reviewer_instruction: str = "") -> ReviewResult:
        return cls(Verdict.REVISE, reviewer_instruction)

    @classmethod
    def abort(cls) -> ReviewResult:
        return cls(Verdict.STOP, "")

    def is_passed(self) -> bool:
        return self.verdict == Verdict.ACCEPT

    def is_failed(self) -> bool:
        return self.verdict == Verdict.REVISE

    def is_aborted(self) -> bool:
        return self.verdict == Verdict.STOP


class Author(ABC):
    """Whoever reviews the results: shown them, answers."""

    @abstractmethod
    def review(self, *results: object) -> ReviewResult: ...


class Review:
    """The review of one stage's results, and the author's confidence in the
    stage: rising a fifth of the way towards certainty with every result the
    author approves, and halving with every result the author has done again;
    never above `CAP`."""

    def __init__(self, author: Author, initial_confidence: float, chance: random.Random) -> None:
        self._author = author
        self.confidence = initial_confidence
        self._chance = chance

    def __call__(self, *results: object) -> ReviewResult:
        """Whether the results pass. They are shown to the author by chance, the
        more likely the less the confidence, and pass unseen, and logged,
        otherwise."""
        logger = logging.getLogger(__name__)
        drawn = self._chance.random()
        if drawn >= 1 - self.confidence:
            logger.info("passed unreviewed, at confidence %.2f", self.confidence)
            unreviewed = ReviewResult.success()
            return unreviewed
        review_result = self._author.review(*results)
        if review_result.is_failed():
            self.confidence = self.confidence / 2
            logger.info("confidence: %.2f", self.confidence)
        elif review_result.is_passed():
            risen = self.confidence + (1 - self.confidence) * RISE
            self.confidence = min(risen, CAP)
            logger.info("confidence: %.2f", self.confidence)
        return review_result
