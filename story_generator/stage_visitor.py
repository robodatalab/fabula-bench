"""What shows the author a stage's draft, and brings back the author's review of
it. `TerminalRenderer` shows it in a terminal; an editor's panel would show it in
its own way."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from story_generator.stages.annotations import Annotations
    from story_generator.stages.choices import Choices
    from story_generator.stages.concepts import Concepts
    from story_generator.stages.high_level_plots import HighLevelPlots
    from story_generator.stages.low_level_plots import LowLevelPlots
    from story_generator.stages.meeting_points import MeetingPoints
    from story_generator.stages.plot_ideas import PlotIdeas
    from story_generator.stages.scenes import Scenes


class Verdict(Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    STOP = "stop"


@dataclass(frozen=True)
class Review:
    """The author's review of a draft; when the draft is to be revised, the
    comment says how."""

    verdict: Verdict
    comment: str = ""


class StageVisitor(ABC):
    @abstractmethod
    def visit_plot_ideas(self, stage: PlotIdeas) -> Review: ...

    @abstractmethod
    def visit_high_level_plots(self, stage: HighLevelPlots) -> Review: ...

    @abstractmethod
    def visit_low_level_plots(self, stage: LowLevelPlots) -> Review: ...

    @abstractmethod
    def visit_meeting_points(self, stage: MeetingPoints) -> Review: ...

    @abstractmethod
    def visit_concepts(self, stage: Concepts) -> Review: ...

    @abstractmethod
    def visit_scenes(self, stage: Scenes) -> Review: ...

    @abstractmethod
    def visit_choices(self, stage: Choices) -> Review: ...

    @abstractmethod
    def visit_annotations(self, stage: Annotations) -> Review: ...
