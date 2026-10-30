"""The workflow of writing a story with its author.

The stages run one after another, each on what the ones before it wrote:

    concepts → plot ends → mesh → scenes → choices

The story is built from its concepts: every concept gets a plot, begun as its
start and its goal; the mesh fills every plot in between, so that the plots meet;
every scene is written towards its events and their plots' concepts, marking the
passages that show them; and the choices that end the scenes come last.

After every stage, the workflow checkpoints which stages are finished, one a
line, in a cell of its own last in the story, of a kind the format does not
know and keeps as it is: stopped in a stage, it resumes at that stage. Going
back to a stage runs it again, and every stage after it.

While a stage runs, whatever is logged under this package goes to the
workflow's handler as that stage's; the workflow logs when the stage starts, and
when it finishes or the author stops in it."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import logging
from pathlib import Path

from authordoc.cells.unknown_cell import UnknownCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.stage import AuthorStopped, Stage
from story_generator.stage_visitor import StageVisitor
from story_generator.stages.choices import Choices
from story_generator.stages.concepts import Concepts
from story_generator.stages.mesh import Mesh
from story_generator.stages.plot_ends import PlotEnds
from story_generator.stages.scenes import Scenes

STAGES = ["concepts", "plot ends", "mesh", "scenes", "choices"]

# The kind of the cell the workflow checkpoints in.
CHECKPOINT = "workflow-checkpoint"


def get_checkpoint(document: Document) -> UnknownCell | None:
    """The cell the workflow checkpoints in; None before its first checkpoint."""
    checkpoint = next(
        (cell for cell in document.cells if isinstance(cell, UnknownCell) and cell.kind == CHECKPOINT),
        None,
    )
    return checkpoint


class Workflow:
    def __init__(self, story: Path, model: CompletionModel, renderer: StageVisitor, handler: logging.Handler) -> None:
        self._story = story
        self._renderer = renderer
        self._handler = handler
        self.stages: dict[str, Stage] = {
            "concepts": Concepts(model),
            "plot ends": PlotEnds(model),
            "mesh": Mesh(model),
            "scenes": Scenes(model),
            "choices": Choices(model),
        }

    def finished(self) -> list[str]:
        """The stages finished so far, as last checkpointed."""
        document = Document.load(self._story)
        checkpoint = get_checkpoint(document)
        if checkpoint is None:
            return []
        finished = checkpoint.source.splitlines()
        return finished

    def run(self, going_back_to: str | None = None) -> None:
        """Runs every stage not finished yet, in order, until the last is finished
        or the author stops in one."""
        logger = logging.getLogger(__name__)
        finished = self.finished()
        if going_back_to is not None:
            at = STAGES.index(going_back_to)
            again = STAGES[at:]
            finished = [name for name in finished if name not in again]
            self._checkpoint(finished)
        for name in STAGES:
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
        """Writes down which stages are finished, in the story's last cell: a stage
        may have added cells after the one checkpointed in before."""
        document = Document.load(self._story)
        held = get_checkpoint(document)
        source = "\n".join(finished)
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
