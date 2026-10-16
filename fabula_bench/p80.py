"""p80: whether a model's answer matches a labelled one (README, "What p80 means").

Two sequences match at p80 when at most 20% of the labelled sequence's elements
are missing from the answered one, and at most 20% of the answered sequence's
elements are not in the labelled one, counting only elements the two share in
the same order. The rule is applied at two levels:

- words within a span: an example, or one span of a plot;
- spans within a plot, where two spans count as the same when their words match
  at p80.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from fractions import Fraction
from typing import TypeVar

# At most this share of either sequence may differ.
MOST_DIFFERING = Fraction(1, 5)

_PUNCTUATION = re.compile(r"[\W_]")

ElementT = TypeVar("ElementT")


def words_of(text: str) -> list[str]:
    """The words of `text`, compared ignoring case and punctuation. A run of
    punctuation standing alone, such as a dash, is not a word."""
    words: list[str] = []
    for written in text.split():
        lowered = written.lower()
        word = _PUNCTUATION.sub("", lowered)
        if word:
            words.append(word)
    return words


def shared_in_order(
    labelled: Sequence[ElementT],
    answered: Sequence[ElementT],
    same: Callable[[ElementT, ElementT], bool],
) -> int:
    """How many elements the two sequences share in the same order: the length
    of their longest common subsequence."""
    previous_row = [0] * (len(answered) + 1)
    for labelled_element in labelled:
        row = [0]
        for answered_index, answered_element in enumerate(answered):
            if same(labelled_element, answered_element):
                shared = previous_row[answered_index] + 1
            else:
                shared = max(previous_row[answered_index + 1], row[answered_index])
            row.append(shared)
        previous_row = row
    longest = previous_row[-1]
    return longest


def at_p80(
    labelled: Sequence[ElementT],
    answered: Sequence[ElementT],
    same: Callable[[ElementT, ElementT], bool],
) -> bool:
    shared = shared_in_order(labelled, answered, same)
    labelled_length = len(labelled)
    answered_length = len(answered)
    missing_from_the_answer = labelled_length - shared
    not_in_the_label = answered_length - shared
    few_missing = missing_from_the_answer <= MOST_DIFFERING * labelled_length
    few_added = not_in_the_label <= MOST_DIFFERING * answered_length
    return few_missing and few_added


def _same_word(labelled_word: str, answered_word: str) -> bool:
    return labelled_word == answered_word


def spans_match(labelled_span: str, answered_span: str) -> bool:
    """Whether an answered example, or one span of a plot, matches a labelled one."""
    labelled_words = words_of(labelled_span)
    answered_words = words_of(answered_span)
    matches = at_p80(labelled_words, answered_words, _same_word)
    return matches


def plot_spans_match(labelled_spans: Sequence[str], answered_spans: Sequence[str]) -> bool:
    """Whether an answered plot's sequence of spans matches a labelled plot's."""
    matches = at_p80(labelled_spans, answered_spans, spans_match)
    return matches
