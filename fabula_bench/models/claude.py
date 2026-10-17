"""Claude, through Anthropic's Messages API.

Credentials resolve the way the SDK resolves them: `ANTHROPIC_API_KEY`, then
`ANTHROPIC_AUTH_TOKEN`, then an `ant auth login` profile.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import anthropic

from fabula_bench.models.base import Model, Turn

_log = logging.getLogger(__name__)

# Room for a long answer after the model has thought. The request is streamed,
# so a large cap cannot run into an HTTP timeout.
DEFAULT_MAX_TOKENS = 64_000

# How many conversations are sent to the API at once.
DEFAULT_CONCURRENCY = 4


class Claude(Model):
    """A Claude model, named by its API id, e.g. `Claude("claude-opus-5-5")`."""

    def __init__(
        self,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        concurrency: int = DEFAULT_CONCURRENCY,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._concurrency = concurrency
        self._client = anthropic.Anthropic() if client is None else client

    def generate(self, conversations: Sequence[Sequence[Turn]]) -> list[str | None]:
        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            replying = pool.map(self._reply_to, conversations)
            replies = list(replying)
        return replies

    def _reply_to(self, conversation: Sequence[Turn]) -> str | None:
        messages: list[Any] = [{"role": turn.role, "content": turn.text} for turn in conversation]
        # No server-side fallback, deliberately: a refusal answered by another
        # model would be recorded as this model's answer.
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=messages,
            ) as stream:
                message = stream.get_final_message()
        except anthropic.APIError as error:
            _log.warning("%s could not answer: %s", self._model, error)
            return None
        if message.stop_reason == "refusal":
            category = None if message.stop_details is None else message.stop_details.category
            _log.warning("%s refused to answer (%s)", self._model, category)
            return None
        texts = [block.text for block in message.content if block.type == "text"]
        reply = "".join(texts)
        return reply
