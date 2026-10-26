from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoryWordRange:
    first_word: int
    last_word: int

    def overlaps(self, other: StoryWordRange) -> bool:
        return self.first_word <= other.last_word and other.first_word <= self.last_word
