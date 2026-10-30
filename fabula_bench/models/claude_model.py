"""Claude, through Anthropic's Messages API, completing a message the way a vramen
`CausalModel` does: one system prompt and one user message in, the reply out.

Credentials resolve the way the SDK resolves them: `ANTHROPIC_API_KEY`, then
`ANTHROPIC_AUTH_TOKEN`, then an `ant auth login` profile.
"""

from __future__ import annotations

import anthropic

# Claude Opus 5.5 always thinks, and its thinking counts against `max_tokens`, so
# a reply is given this much room on top of the room it asks for. The higher the
# effort, the more it thinks.
THINKING_ROOM_TOKENS = 32_000


class ClaudeModel:
    """`effort` is how hard the model thinks before it replies: "low", "medium",
    "high", "xhigh" or "max"."""

    def __init__(self, model_id: str, effort: str) -> None:
        self.model_id = model_id
        self._effort = effort
        self._client = anthropic.Anthropic()

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        # Streamed, a request may take longer than the 10 minutes the SDK allows
        # one that is not. No server-side fallback, deliberately: a refusal
        # answered by another model would be recorded as this model's answer.
        with self._client.messages.stream(
            model=self.model_id,
            max_tokens=max_new_tokens + THINKING_ROOM_TOKENS,
            output_config={"effort": self._effort},
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
        texts = [block.text for block in message.content if block.type == "text"]
        reply = "".join(texts)
        return reply
