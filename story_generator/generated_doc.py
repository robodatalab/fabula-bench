"""A story being generated, saved with the checkpoint of where its generation
stands."""

from __future__ import annotations

from pathlib import Path

from authordoc.cells.unknown_cell import UnknownCell
from authordoc.storydoc import Document

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
