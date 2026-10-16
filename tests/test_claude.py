import unittest
from types import SimpleNamespace
from typing import Any

from fabula_bench.models.base import Turn
from fabula_bench.models.claude import Claude


class _Stream:
    def __init__(self, message: SimpleNamespace) -> None:
        self._message = message

    def __enter__(self) -> "_Stream":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_final_message(self) -> SimpleNamespace:
        return self._message


class _AnthropicClient:
    """Stands in for `anthropic.Anthropic`: answers every request with `content`,
    or with the text of the conversation's last turn when `content` is None."""

    def __init__(self, content: list[SimpleNamespace] | None = None, stop_reason: str = "end_turn") -> None:
        self._content = content
        self._stop_reason = stop_reason
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **request: Any) -> _Stream:
        self.requests.append(request)
        last_turn = request["messages"][-1]["content"]
        echoed = [SimpleNamespace(type="text", text=last_turn)]
        content = echoed if self._content is None else self._content
        stop_details = SimpleNamespace(category="cyber") if self._stop_reason == "refusal" else None
        message = SimpleNamespace(stop_reason=self._stop_reason, stop_details=stop_details, content=content)
        return _Stream(message)


CONVERSATION = [Turn("user", "Who knocked?")]


class Generate(unittest.TestCase):
    def test_sends_the_model_its_conversation(self) -> None:
        client = _AnthropicClient()
        claude = Claude("claude-opus-5-5", max_tokens=1000, client=client)

        claude.generate([CONVERSATION])

        (request,) = client.requests
        self.assertEqual(request["model"], "claude-opus-5-5")
        self.assertEqual(request["max_tokens"], 1000)
        self.assertEqual(request["messages"], [{"role": "user", "content": "Who knocked?"}])

    def test_replies_with_the_text_and_nothing_the_model_thought(self) -> None:
        content = [
            SimpleNamespace(type="thinking", thinking="Michael, probably."),
            SimpleNamespace(type="text", text="Nobody "),
            SimpleNamespace(type="text", text="answered."),
        ]
        claude = Claude("claude-opus-5-5", client=_AnthropicClient(content))

        replies = claude.generate([CONVERSATION])

        self.assertEqual(replies, ["Nobody answered."])

    def test_replies_to_each_conversation_in_the_order_given(self) -> None:
        conversations = [[Turn("user", f"Story {index}")] for index in range(10)]
        claude = Claude("claude-opus-5-5", concurrency=4, client=_AnthropicClient())

        replies = claude.generate(conversations)

        expected = [f"Story {index}" for index in range(10)]
        self.assertEqual(replies, expected)

    def test_stops_with_an_error_when_the_model_refuses(self) -> None:
        claude = Claude("claude-opus-5-5", client=_AnthropicClient(stop_reason="refusal"))

        with self.assertRaisesRegex(RuntimeError, "refused to answer \\(cyber\\)"):
            claude.generate([CONVERSATION])
