"""The author's side of writing a story, in a terminal: each stage's draft printed
with what the author needs to judge it, and the author's review read from the
keyboard."""

from __future__ import annotations

from story_generator.stage_visitor import Review, StageVisitor, Verdict
from story_generator.stages.choices import Choices
from story_generator.stages.concept_arcs import ConceptArcs
from story_generator.stages.concepts import Concepts
from story_generator.stages.mesh import Mesh
from story_generator.stages.plot_ends import PlotEnds
from story_generator.stages.scenes import Scenes
from story_generator.stages.validity import Validity

STOP = "q"

# How much of the end of a scene is shown above its choices.
SCENE_TAIL = 600


class TerminalRenderer(StageVisitor):
    def visit_concepts(self, stage: Concepts) -> Review:
        if not stage.concept:
            titles = stage.draft or "(none yet: say what the story is about)"
            print(f"\n== What the story is about ==\n\n{titles}\n")
        else:
            heading = _heading(f"Concept: {stage.concept}", stage.progress)
            print(f"{heading}\n{stage.draft}\n")
        review = _review()
        return review

    def visit_plot_ends(self, stage: PlotEnds) -> Review:
        heading = _heading(f"Ends of the plot of {stage.concept}", stage.progress)
        print(f"{heading}\n{stage.description}\n\nmoment | place | what happens\n{stage.draft}\n")
        review = _review()
        return review

    def visit_mesh(self, stage: Mesh) -> Review:
        heading = _heading(f"Mesh of {stage.plot}, which illustrates {stage.concepts}", stage.progress)
        print(
            f"{heading}\n{stage.description}\n\n"
            f"Where it meets the other plots now:\n{stage.meetings}\n\n"
            f"Its events now:\n{stage.events_now}\n\nFilled in:\n{stage.draft}\n"
        )
        review = _review()
        return review

    def visit_concept_arcs(self, stage: ConceptArcs) -> Review:
        heading = _heading(f"Concept arcs of {stage.plot}", stage.progress)
        print(f"{heading}\n{stage.description}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_scenes(self, stage: Scenes) -> Review:
        heading = _heading(f"Scene at {stage.moment}, {stage.place}", stage.progress)
        happening = "\n".join(f"- {plot}: {summary} ({concepts})" for plot, summary, concepts in stage.towards)
        under_review = stage.under_review
        if stage.version_event:
            concept = stage.version_concept or "none"
            under_review = f"{under_review}\nConcept: {concept}\nPlot: {stage.version_plot}\nEvent: {stage.version_event}"
            if stage.version_shows:
                under_review = f"{under_review}\nHow it shows here: {stage.version_shows}"
        print(f"{heading}\nWhat happens:\n{happening}\n\n{under_review}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_choices(self, stage: Choices) -> Review:
        heading = _heading("Choices", stage.progress)
        leading_to = "\n".join(f"- {summary}" for summary in stage.leading_to)
        tail = stage.scene[-SCENE_TAIL:]
        print(f"{heading}\n…{tail}\n\nLeading to:\n{leading_to}\n\n{stage.draft}\n")
        review = _review()
        return review

    def visit_validity(self, stage: Validity) -> Review:
        print(f"\n== Validity of the story ==\n\n{stage.draft}\n")
        review = _accepted_or_stopped()
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


def _accepted_or_stopped() -> Review:
    """The author's verdict on what there is no draft of to revise."""
    answer = input(f"[a]ccept  [{STOP}] stop > ")
    choice = answer.strip().lower()
    while choice not in ("a", STOP):
        answer = input(f"a or {STOP} > ")
        choice = answer.strip().lower()
    verdict = Verdict.ACCEPT if choice == "a" else Verdict.STOP
    review = Review(verdict)
    return review
