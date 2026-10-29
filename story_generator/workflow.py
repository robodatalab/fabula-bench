"""The workflow of writing a story with its author.

The stages run in this order:

    plot ideas → high-level plots → low-level plots ─┬→ meeting points → scenes → choices ─┬→ annotations
                                                      └→ concepts ─────────────────────────┘

The concepts depend on the low-level plots alone, beside the branch that writes
the scenes; the annotations need both branches. The author works through one
stage at a time, so the two branches run one after the other.

After every stage, the workflow checkpoints which stages are finished, in a file
beside the story: stopped in a stage, it resumes at that stage. Going back to a
stage runs it again, and every stage that depends on it, and no other.

While a stage runs, whatever is logged under this package goes to the
workflow's handler as that stage's; the workflow logs when the stage starts, and
when it finishes or the author stops in it."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import json
import logging
from pathlib import Path

from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import AuthorStopped, Stage
from story_generator.stage_visitor import StageVisitor
from story_generator.stages.annotations import Annotations
from story_generator.stages.choices import Choices
from story_generator.stages.concepts import Concepts
from story_generator.stages.high_level_plots import HighLevelPlots
from story_generator.stages.low_level_plots import LowLevelPlots
from story_generator.stages.meeting_points import MeetingPoints
from story_generator.stages.plot_ideas import PlotIdeas
from story_generator.stages.scenes import Scenes

TRUNK = ["plot ideas", "high-level plots", "low-level plots"]
SCENES_BRANCH = ["meeting points", "scenes", "choices"]
CONCEPTS_BRANCH = ["concepts"]
JOIN = ["annotations"]
PARTS = (TRUNK, SCENES_BRANCH, CONCEPTS_BRANCH, JOIN)


class Workflow:
    def __init__(self, story: Path, model: CompletionModel, renderer: StageVisitor, handler: logging.Handler) -> None:
        self._story = story
        self._checkpoint_path = story.with_suffix(".workflow.json")
        self._renderer = renderer
        self._handler = handler
        self.stages: dict[str, Stage] = {
            "plot ideas": PlotIdeas(),
            "high-level plots": HighLevelPlots(model),
            "low-level plots": LowLevelPlots(model),
            "meeting points": MeetingPoints(model),
            "scenes": Scenes(model),
            "choices": Choices(model),
            "concepts": Concepts(model),
            "annotations": Annotations(model),
        }

    def finished(self) -> list[str]:
        """The stages finished so far, as last checkpointed."""
        if not self._checkpoint_path.exists():
            return []
        written = self._checkpoint_path.read_text(encoding="utf-8")
        finished: list[str] = json.loads(written)
        return finished

    def run(self, going_back_to: str | None = None) -> None:
        """Runs every stage not finished yet, in order, until the last is finished
        or the author stops in one."""
        logger = logging.getLogger(__name__)
        finished = self.finished()
        if going_back_to is not None:
            again = _depending_on(going_back_to)
            finished = [name for name in finished if name not in again]
            self._checkpoint(finished)
        for part in PARTS:
            for name in part:
                if name in finished:
                    continue
                stage = self.stages[name]
                with _logged_as(name, self._handler):
                    logger.info("started")
                    try:
                        stage.run(story=self._story, renderer=self._renderer)
                    except AuthorStopped:
                        logger.info("stopped")
                        return
                    logger.info("finished")
                finished.append(name)
                self._checkpoint(finished)

    def _checkpoint(self, finished: list[str]) -> None:
        """Writes down which stages are finished, beside the story."""
        written = json.dumps(finished, indent=2)
        self._checkpoint_path.write_text(written, encoding="utf-8")


def _depending_on(stage: str) -> list[str]:
    """The stage, and every stage that depends on it: the rest of its own part of
    the workflow, and every part after it that needs it."""
    part = next(part for part in PARTS if stage in part)
    at = part.index(stage)
    rest = part[at:]
    if part is TRUNK:
        return [*rest, *SCENES_BRANCH, *CONCEPTS_BRANCH, *JOIN]
    if part is JOIN:
        return rest
    return [*rest, *JOIN]


@contextmanager
def _logged_as(stage: str, handler: logging.Handler) -> Generator[None]:
    """While inside, whatever is logged under this package goes to the handler,
    every record stamped with the stage's name as `record.stage`."""

    def stamped(record: logging.LogRecord) -> bool:
        record.stage = stage
        return True

    package_logger = logging.getLogger(__package__)
    package_logger.setLevel(logging.INFO)
    handler.addFilter(stamped)
    package_logger.addHandler(handler)
    try:
        yield
    finally:
        package_logger.removeHandler(handler)
        handler.removeFilter(stamped)
