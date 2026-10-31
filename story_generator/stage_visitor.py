"""What shows the author a stage's draft, and brings back the author's review of
it. `TerminalRenderer` shows it in a terminal; an editor's panel would show it in
its own way."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from story_generator.stages.choices import Choices
    from story_generator.stages.concept_arcs import ConceptArcs
    from story_generator.stages.concepts import Concepts
    from story_generator.stages.mesh import Mesh
    from story_generator.stages.plot_ends import PlotEnds
    from story_generator.stages.scenes import Scenes
    from story_generator.stages.validity import Validity


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
    def visit_concepts(self, stage: Concepts) -> Review: ...

    @abstractmethod
    def visit_plot_ends(self, stage: PlotEnds) -> Review: ...

    @abstractmethod
    def visit_mesh(self, stage: Mesh) -> Review: ...

    @abstractmethod
    def visit_concept_arcs(self, stage: ConceptArcs) -> Review: ...

    @abstractmethod
    def visit_scenes(self, stage: Scenes) -> Review: ...

    @abstractmethod
    def visit_choices(self, stage: Choices) -> Review: ...

    @abstractmethod
    def visit_validity(self, stage: Validity) -> Review:
        """The author's verdict on the story, as the report finds it: accepted, or
        stopped at; there is no draft to revise."""
