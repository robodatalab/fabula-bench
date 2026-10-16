"""A model, as the benchmark holds it: conversations in, replies out.

`Model` stands for every model the benchmark can run — Claude behind an API, or
a model a developer is working on in their own process — so it asks only for
what every model can do. There is no system role, because not every model's
chat template has one (Gemma's does not), and no sampling settings, because
several reasoning models reject a temperature. Whatever a particular model is
run with belongs to that model's class.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Turn:
    """One turn of a conversation."""

    role: Role
    text: str


class Model(abc.ABC):
    """A model the benchmark can run: subclass it to run your own."""

    @abc.abstractmethod
    def generate(self, conversations: Sequence[Sequence[Turn]]) -> list[str]:
        """The model's reply to each conversation, in the same order.

        The conversations come as a batch so that a model running on its own
        hardware can generate for several at once."""
