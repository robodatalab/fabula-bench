"""Claude, through Anthropic's Messages API, completing a message the way a vramen
`CausalModel` does: one system prompt and one user message in, the reply out.

Credentials resolve the way the SDK resolves them: `ANTHROPIC_API_KEY`, then
`ANTHROPIC_AUTH_TOKEN`, then an `ant auth login` profile.
"""

from __future__ import annotations

import anthropic

# Claude Opus 5.5 always thinks, and its thinking counts against `max_tokens`, so
# a reply is given this much room on top of the room it asks for.
THINKING_ROOM_TOKENS = 16_000


class ClaudeModel:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self._client = anthropic.Anthropic()

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        # No server-side fallback, deliberately: a refusal answered by another
        # model would be recorded as this model's answer.
        message = self._client.messages.create(
            model=self.model_id,
            max_tokens=max_new_tokens + THINKING_ROOM_TOKENS,
            output_config={"effort": "low"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        texts = [block.text for block in message.content if block.type == "text"]
        reply = "".join(texts)
        return reply
