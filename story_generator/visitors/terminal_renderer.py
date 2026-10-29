"""The author's side of writing a story, in a terminal: each stage's draft printed
with what the author needs to judge it, and the author's review read from the
keyboard."""

from __future__ import annotations

from story_generator.stage_visitor import Review, StageVisitor, Verdict
from story_generator.stages.annotations import Annotations
from story_generator.stages.choices import Choices
from story_generator.stages.concepts import Concepts
from story_generator.stages.high_level_plots import HighLevelPlots
from story_generator.stages.low_level_plots import LowLevelPlots
from story_generator.stages.meeting_points import MeetingPoints
from story_generator.stages.plot_ideas import PlotIdeas
from story_generator.stages.scenes import Scenes

STOP = "q"

# How much of the end of a scene is shown above its choices.
SCENE_TAIL = 600


class TerminalRenderer(StageVisitor):
    def visit_plot_ideas(self, stage: PlotIdeas) -> Review:
        ideas = stage.draft or "(none yet)"
        print(f"\n== Plot ideas ==\n\n{ideas}\n")
        answer = input(f"Another idea, in one paragraph (empty to accept the ideas, {STOP} to stop) > ")
        idea = answer.strip()
        if idea == "":
            accepted = Review(Verdict.ACCEPT)
            return accepted
        if idea == STOP:
            stopped = Review(Verdict.STOP)
            return stopped
        added = Review(Verdict.REVISE, idea)
        return added

    def visit_high_level_plots(self, stage: HighLevelPlots) -> Review:
        heading = _heading("Outline", stage.progress)
        print(f"{heading}\nThe idea: {stage.idea}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_low_level_plots(self, stage: LowLevelPlots) -> Review:
        heading = _heading("Events", stage.progress)
        print(f"{heading}\n{stage.outline}\n\nmoment | place | what happens\n{stage.draft}\n")
        review = _review()
        return review

    def visit_meeting_points(self, stage: MeetingPoints) -> Review:
        heading = _heading(f"Meeting points of {stage.title}", stage.progress)
        print(
            f"{heading}\nWhere it meets the other plots now:\n{stage.meetings}\n\n"
            f"Its events now:\n{stage.events_now}\n\nRevised:\n{stage.draft}\n"
        )
        review = _review()
        return review

    def visit_concepts(self, stage: Concepts) -> Review:
        heading = _heading(f"Concepts of {stage.title}", stage.progress)
        print(f"{heading}\n{stage.draft}\n")
        review = _review()
        return review

    def visit_scenes(self, stage: Scenes) -> Review:
        heading = _heading(f"Scene at {stage.moment}, {stage.place}", stage.progress)
        happening = "\n".join(f"- {summary}" for summary in stage.happening)
        print(f"{heading}\nWhat happens:\n{happening}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_choices(self, stage: Choices) -> Review:
        heading = _heading("Choices", stage.progress)
        leading_to = "\n".join(f"- {summary}" for summary in stage.leading_to)
        tail = stage.scene[-SCENE_TAIL:]
        print(f"{heading}\n…{tail}\n\nLeading to:\n{leading_to}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_annotations(self, stage: Annotations) -> Review:
        heading = _heading(f"Passages showing {stage.concept}", stage.progress)
        numbered = [f"{number}. {passage}" for number, passage in enumerate(stage.passages, start=1)]
        passages = "\n\n".join(numbered) or "(none found)"
        print(f"{heading}\n{stage.description}\n\n{passages}\n")
        review = _review()
        return review


def _heading(title: str, progress: tuple[int, int]) -> str:
    done, total = progress
    heading = f"\n== {title} ({done + 1} of {total}) ==\n"
    return heading


def _review() -> Review:
    """The author's verdict on a draft, and what to change when it is to be
    revised."""
    answer = input(f"[a]ccept  [r]evise  [{STOP}] stop > ")
    choice = answer.strip().lower()
    while choice not in ("a", "r", STOP):
        answer = input(f"a, r or {STOP} > ")
        choice = answer.strip().lower()
    if choice == "a":
        accepted = Review(Verdict.ACCEPT)
        return accepted
    if choice == STOP:
        stopped = Review(Verdict.STOP)
        return stopped
    comment = input("What should change? > ")
    revised = Review(Verdict.REVISE, comment)
    return revised
