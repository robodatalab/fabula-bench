"""The workflow of writing a story with its author.

The stages run one after another, each on what the ones before it wrote:

    concepts → plot ends → mesh → concept arcs → scenes → choices

The story is built from its concepts: every concept gets a plot, begun as its
start and its goal; the mesh fills every plot in between, so that the plots meet;
the concept arcs say how every concept shows at every event of its plot; every
scene is built from versions dedicated to the concepts that show at its events,
merged between the concepts' markers; and the choices that end the scenes come
last.

After every stage, and when the author stops, the workflow checkpoints which
stages are finished, one a line, and the author's confidence in every kind of
draft, in a cell of its own last in the story, of a kind the format does not
know and keeps as it is: stopped in a stage, it resumes at that stage, as
confident as it was. Going back to a stage runs it again, and every stage after
it.

While a stage runs, whatever is logged under this package goes to the
workflow's handler as that stage's; the workflow logs when the stage starts, and
when it finishes or the author stops in it."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import logging
import random
from pathlib import Path

from authordoc.cells.unknown_cell import UnknownCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import AuthorStopped, Confidence, Stage
from story_generator.stage_visitor import StageVisitor
from story_generator.stages.choices import Choices
from story_generator.stages.concept_arcs import ConceptArcs
from story_generator.stages.concepts import Concepts
from story_generator.stages.mesh import Mesh
from story_generator.stages.plot_ends import PlotEnds
from story_generator.stages.scenes import Scenes

STAGES = ["concepts", "plot ends", "mesh", "concept arcs", "scenes", "choices"]

# The kind of the cell the workflow checkpoints in.
CHECKPOINT = "workflow-checkpoint"

# Opens a line of the checkpoint that keeps the confidence in a kind of draft, as
# in "confidence in scene versions: 0.672".
CONFIDENCE = "confidence in "


def get_checkpoint(document: Document) -> UnknownCell | None:
    """The cell the workflow checkpoints in; None before its first checkpoint."""
    checkpoint = next(
        (cell for cell in document.cells if isinstance(cell, UnknownCell) and cell.kind == CHECKPOINT),
        None,
    )
    return checkpoint


class Workflow:
    def __init__(
        self,
        story: Path,
        model: CompletionModel,
        renderer: StageVisitor,
        handler: logging.Handler,
        chance: random.Random | None = None,
    ) -> None:
        self._story = story
        self._renderer = renderer
        self._handler = handler
        # What draws the drafts the author reviews.
        self._chance = chance if chance is not None else random.Random()
        self.stages: dict[str, Stage] = {
            "concepts": Concepts(model),
            "plot ends": PlotEnds(model),
            "mesh": Mesh(model),
            "concept arcs": ConceptArcs(model),
            "scenes": Scenes(model),
            "choices": Choices(model),
        }

    def finished(self) -> list[str]:
        """The stages finished so far, as last checkpointed."""
        lines = self._checkpointed()
        finished = [line for line in lines if not line.startswith(CONFIDENCE)]
        return finished

    def confidence(self) -> Confidence:
        """The author's confidence in every kind of draft, as last checkpointed."""
        lines = self._checkpointed()
        levels = {}
        for line in lines:
            if not line.startswith(CONFIDENCE):
                continue
            written = line.removeprefix(CONFIDENCE)
            kind, _, written_level = written.rpartition(": ")
            levels[kind] = float(written_level)
        confidence = Confidence(levels, self._chance)
        return confidence

    def run(self, going_back_to: str | None = None) -> None:
        """Runs every stage not finished yet, in order, until the last is finished
        or the author stops in one."""
        logger = logging.getLogger(__name__)
        finished = self.finished()
        confidence = self.confidence()
        if going_back_to is not None:
            at = STAGES.index(going_back_to)
            again = STAGES[at:]
            finished = [name for name in finished if name not in again]
            self._checkpoint(finished, confidence)
        for name in STAGES:
            if name in finished:
                continue
            stage = self.stages[name]
            with _logged_as(name, self._handler):
                logger.info("started")
                try:
                    stage.run(story=self._story, renderer=self._renderer, confidence=confidence)
                except AuthorStopped:
                    logger.info("stopped")
                    self._checkpoint(finished, confidence)
                    return
                logger.info("finished")
            finished.append(name)
            self._checkpoint(finished, confidence)

    def _checkpointed(self) -> list[str]:
        """The lines of the checkpoint; none before the first."""
        document = Document.load(self._story)
        checkpoint = get_checkpoint(document)
        if checkpoint is None:
            return []
        lines = checkpoint.source.splitlines()
        return lines

    def _checkpoint(self, finished: list[str], confidence: Confidence) -> None:
        """Writes down which stages are finished, and the confidence in every kind
        of draft, in the story's last cell: a stage may have added cells after the
        one checkpointed in before."""
        document = Document.load(self._story)
        held = get_checkpoint(document)
        levels = sorted(confidence.levels.items())
        confident = [f"{CONFIDENCE}{kind}: {level:.3f}" for kind, level in levels]
        source = "\n".join([*finished, *confident])
        checkpoint = UnknownCell(CHECKPOINT, source=source) if held is None else held.with_source(source)
        others = [cell for cell in document.cells if cell.unique_id != checkpoint.unique_id]
        cells = [*others, checkpoint]
        written = Document.from_cells(cells, document.path)
        self._story.write_text(written.text, encoding="utf-8")


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
