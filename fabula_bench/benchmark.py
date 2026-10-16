"""Running the benchmark: every story's tasks asked of a model, and every answer
read into the same shape as the story's labels, so that the two can be compared.

A story with salient concepts labelled is asked for its salient concepts and
their examples — tasks 1 and 2, in one answer. A story with plots labelled is
asked for its plots — task 3. Scoring is not written yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fabula_bench import storydoc
from fabula_bench.labels import StoryLabels, labels_of
from fabula_bench.models.base import Model, Turn

CONCEPTS_PROMPT = """<story>
{story}
</story>

Enumerate all the salient concepts of the story above, each with a brief \
explanation. For each concept, also give its examples: the places in the story \
that correspond to it, each quoted word for word from the story.

Answer with a single JSON object and nothing else, in this shape:

{{"concepts": [{{"title": "...", "description": "...", "examples": ["...", "..."]}}]}}"""

PLOTS_PROMPT = """<story>
{story}
</story>

List the plots of the story above. For each plot, give its name, a description, \
and the spans of the story's text that form it, in order, each quoted word for \
word from the story. Copied out in the order you give them, the spans must read \
as a complete substory.

Answer with a single JSON object and nothing else, in this shape:

{{"plots": [{{"title": "...", "description": "...", "spans": ["...", "..."]}}]}}"""

CONCEPTS = "concepts"
PLOTS = "plots"


@dataclass(frozen=True)
class AnsweredConcept:
    title: str
    description: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class AnsweredPlot:
    title: str
    description: str
    spans: tuple[str, ...]


@dataclass(frozen=True)
class StoryAnswers:
    """What a model answered about one story, beside the story's labels."""

    story: Path
    labels: StoryLabels
    concepts: tuple[AnsweredConcept, ...]
    plots: tuple[AnsweredPlot, ...]
    # The model's replies as it wrote them, and what in them could not be read.
    replies: tuple[str, ...]
    problems: tuple[str, ...]


def evaluate(model: Model, stories: Path) -> list[StoryAnswers]:
    """Ask `model` every task the stories under `stories` — a directory of
    `.author` files — have labels for. A story is asked for its concepts when it
    has salient concepts labelled, and for its plots when it has plots labelled;
    only then can the answer be scored. All the questions go to the model in one
    batch."""
    found = stories.rglob(f"*{storydoc.EXTENSION}")
    story_paths = sorted(found)
    documents = [storydoc.Document.load(path) for path in story_paths]
    labels_of_each_story = [labels_of(document) for document in documents]
    questions: list[tuple[int, str]] = []
    conversations: list[list[Turn]] = []
    stories_with_labels = zip(documents, labels_of_each_story)
    for story_index, (document, labels) in enumerate(stories_with_labels):
        prose = _prose_of(document)
        if labels.concepts:
            concepts_conversation = _conversation(CONCEPTS_PROMPT, prose)
            questions.append((story_index, CONCEPTS))
            conversations.append(concepts_conversation)
        if labels.plots:
            plots_conversation = _conversation(PLOTS_PROMPT, prose)
            questions.append((story_index, PLOTS))
            conversations.append(plots_conversation)
    replies = model.generate(conversations)
    replies_to_questions = zip(questions, replies, strict=True)
    reply_to_each_question = dict(replies_to_questions)
    asked_stories = sorted({story_index for story_index, _ in questions})
    answers = [
        _story_answers(
            story_paths[story_index],
            labels_of_each_story[story_index],
            story_index,
            reply_to_each_question,
        )
        for story_index in asked_stories
    ]
    return answers


def _prose_of(document: storydoc.Document) -> str:
    # The story as a reader of the book sees it: its prose, without the labels,
    # which live in cells of their own.
    markdown_cells = document.markdown_cells()
    prose_of_each_cell = [cell.source for cell in markdown_cells]
    prose = "\n\n".join(prose_of_each_cell)
    return prose


def _conversation(prompt: str, prose: str) -> list[Turn]:
    asked = prompt.format(story=prose)
    user_turn = Turn("user", asked)
    conversation = [user_turn]
    return conversation


def _story_answers(
    story: Path,
    labels: StoryLabels,
    story_index: int,
    reply_to_each_question: dict[tuple[int, str], str],
) -> StoryAnswers:
    concepts_reply = reply_to_each_question.get((story_index, CONCEPTS))
    plots_reply = reply_to_each_question.get((story_index, PLOTS))
    replies: list[str] = []
    problems: list[str] = []
    concepts: tuple[AnsweredConcept, ...] = ()
    plots: tuple[AnsweredPlot, ...] = ()
    if concepts_reply is not None:
        replies.append(concepts_reply)
        answered_concepts = _answered_entries(concepts_reply, CONCEPTS, "examples", problems)
        concepts_in_the_reply = [AnsweredConcept(*entry) for entry in answered_concepts]
        concepts = tuple(concepts_in_the_reply)
    if plots_reply is not None:
        replies.append(plots_reply)
        answered_plots = _answered_entries(plots_reply, PLOTS, "spans", problems)
        plots_in_the_reply = [AnsweredPlot(*entry) for entry in answered_plots]
        plots = tuple(plots_in_the_reply)
    all_replies = tuple(replies)
    all_problems = tuple(problems)
    story_answers = StoryAnswers(story, labels, concepts, plots, all_replies, all_problems)
    return story_answers


def _answered_entries(
    reply: str, list_name: str, quotes_name: str, problems: list[str]
) -> list[tuple[str, str, tuple[str, ...]]]:
    """The entries of the list called `list_name` in the JSON object `reply`
    holds, each as its title, description and quotes. What does not fit that
    shape is left out and said in `problems`."""
    answer = _json_object_in(reply)
    if answer is None:
        problems.append(f"the {list_name} reply holds no JSON object")
        return []
    written_entries = answer.get(list_name)
    if not isinstance(written_entries, list):
        problems.append(f"the {list_name} reply has no list called {list_name!r}")
        return []
    entries: list[tuple[str, str, tuple[str, ...]]] = []
    for written_entry in written_entries:
        entry = _entry_in(written_entry, quotes_name)
        if entry is None:
            problems.append(f"left out a {list_name} entry not in the asked shape: {written_entry}")
            continue
        entries.append(entry)
    return entries


def _json_object_in(reply: str) -> dict[str, Any] | None:
    # The object runs from the first opening brace to the last closing one, so
    # a code fence or a sentence around it does not matter.
    first_brace = reply.find("{")
    last_brace = reply.rfind("}")
    if first_brace < 0 or last_brace < first_brace:
        return None
    written_object = reply[first_brace : last_brace + 1]
    try:
        answer = json.loads(written_object)
    except json.JSONDecodeError:
        return None
    if not isinstance(answer, dict):
        return None
    return answer


def _entry_in(written_entry: Any, quotes_name: str) -> tuple[str, str, tuple[str, ...]] | None:
    if not isinstance(written_entry, dict):
        return None
    title = written_entry.get("title")
    description = written_entry.get("description")
    quotes = written_entry.get(quotes_name)
    has_the_asked_shape = (
        isinstance(title, str) and isinstance(description, str) and isinstance(quotes, list)
    )
    if not has_the_asked_shape:
        return None
    if not all(isinstance(quote, str) for quote in quotes):
        return None
    quoted = tuple(quotes)
    entry = (title, description, quoted)
    return entry
