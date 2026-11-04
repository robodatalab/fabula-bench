"""The workflow of writing a story with its author.

The stages run one after another, each on what the ones before it wrote:

    concepts → plot ends → mesh → concept arcs → scenes → choices → validity

The story is built from its concepts: every concept gets a plot, begun as its
start and its goal; the mesh fills every plot in between, so that the plots meet;
the concept arcs say how every concept shows at every event of its plot; every
scene is built from versions dedicated to the concepts that show at its events,
merged between the concepts' markers; and the choices that end the scenes come
after them. Last, the story is played as the benchmark plays it, to check that
it does what the benchmark needs of it.

A stage only plans its work as steps. Everything else happens here: the steps
run one after another, each done again with the author's instruction until its
result passes its review; after every step, the story is saved, with the
checkpoint of where the generation stands; and the stage's progress is shown.
Stopped in a stage, or killed in it, the workflow resumes at that stage, from its
first step, as confident in the stage as it was.

While a stage runs, whatever is logged under this package goes to the
workflow's handler as that stage's; the workflow logs when the stage starts, and
when it finishes or the author stops in it."""

from __future__ import annotations

import logging
import random
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from tqdm import tqdm

from authordoc.cells.unknown_cell import UnknownCell
from authordoc.storydoc import Document
from fabula_bench.players.agent_player import CompletionModel
from story_generator.review import ReviewResult, TerminalReview
from story_generator.stage import Stage
from story_generator.stages.choices import Choices
from story_generator.stages.concept_arcs import ConceptArcs
from story_generator.stages.concepts import Concepts
from story_generator.stages.mesh import Mesh
from story_generator.stages.plot_ends import PlotEnds
from story_generator.stages.scenes import Scenes
from story_generator.stages.validity import Validity

STAGES = ["concepts", "plot ends", "mesh", "concept arcs", "scenes", "choices", "validity"]

# The kind of the cell the checkpoint is kept in.
CHECKPOINT = "GeneratedDocumentCheckpoint"

# Open the lines of the checkpoint, as in "stage: mesh: True" and
# "confidence in mesh: 0.360".
STAGE = "stage: "
CONFIDENCE = "confidence in "


class GeneratedDocument:
    """A story being generated: the story, kept in its .author file, and where its
    generation stands, kept in the checkpoint, a cell of its own last in the
    story, of a kind the format does not know and keeps as it is: which stages
    are finished, and the author's confidence in every stage."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.document = Document.load(self._path)
        self.stages: dict[str, bool] = {name: False for name in STAGES}
        self.confidence: dict[str, float] = {name: 0.0 for name in STAGES}

    def load(self) -> None:
        """Reads the story from its file, and where its generation stands from its
        checkpoint."""
        self.document = Document.load(self._path)
        checkpoint = self.document.get_cell(UnknownCell, CHECKPOINT)
        lines = checkpoint.source.splitlines() if checkpoint is not None else []

        self.stages = {name: False for name in STAGES}
        self.confidence = {name: 0.0 for name in STAGES}

        for line in lines:
            if line.startswith(STAGE):
                value = line.removeprefix(STAGE)
                stage, _, is_done = value.rpartition(": ")
                self.stages[stage] = is_done == "True"

            elif line.startswith(CONFIDENCE):
                value = line.removeprefix(CONFIDENCE)
                stage, _, level = value.rpartition(": ")
                self.confidence[stage] = float(level)

    def save(self) -> None:
        """Writes the story into its file, with the checkpoint as its last cell: a
        stage may have added cells after the one it was kept in before."""
        lines = []

        for stage, is_done in self.stages.items():
            lines.append(f"{STAGE}{stage}: {is_done}")

        for stage, level in sorted(self.confidence.items()):
            lines.append(f"{CONFIDENCE}{stage}: {level:.3f}")

        source = "\n".join(lines)

        held = self.document.get_cell(UnknownCell, CHECKPOINT)
        checkpoint = UnknownCell(CHECKPOINT, source=source) if held is None else held.with_source(source)
        others = [cell for cell in self.document.cells if cell.unique_id != checkpoint.unique_id]
        self.document = Document.from_cells([*others, checkpoint], self._path)
        self.document.save()

    def next_stage(self) -> str | None:
        for stage_name in STAGES:
            if not self.stages[stage_name]:
                return stage_name
        return None

    def mark_stage_done(self, stage_name: str) -> None:
        self.stages[stage_name] = True
    

class Workflow:
    def __init__(
        self,
        path: Path,
        model: CompletionModel,
        handler: logging.Handler,
        chance: random.Random | None = None,
    ) -> None:
        self._handler = handler
        # What draws the results the author reviews.
        self._chance = chance if chance is not None else random.Random()
        self.stages: dict[str, Stage] = {
            "concepts": Concepts(model),
            "plot ends": PlotEnds(model),
            "mesh": Mesh(model),
            "concept arcs": ConceptArcs(model),
            "scenes": Scenes(model),
            "choices": Choices(model),
            "validity": Validity(),
        }

        self._document = GeneratedDocument(path)


    def run(self) -> None:
        """Runs every stage not finished yet, in order, until the last is finished
        or the author stops in one."""
        logger = logging.getLogger(__name__)

        self._document.load()
        
        stage_name = self._document.next_stage()
        stage_aborted = False
        while stage_name and not stage_aborted:
            stage = self.stages[stage_name]
            initial_confidence = self._document.confidence.get(stage_name, 0.0)
            reviews = TerminalReview(initial_confidence, self._chance)

            with _logged_as(stage_name, self._handler):
                logger.info("started")
                steps = stage.run(self._document.document)

                for step in tqdm(steps, desc=stage_name):
                    review_result = ReviewResult.failed()
                    document = self._document.document
                    while review_result.is_failed():
                        review_result, document = step(self._document.document, reviews, review_result.comment)

                    if review_result.is_passed():
                        self._document.document = document
                        self._document.confidence[stage_name] = reviews.confidence
                        self._document.save()
                    else:
                        stage_aborted = True
                        break

                logger.info("finished")

            if not stage_aborted:
                self._document.mark_stage_done(stage_name)
                self._document.save()
                stage_name =  self._document.next_stage()


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
