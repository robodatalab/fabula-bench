from collections.abc import Sequence

from authordoc.cells.plot_cell import PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell, SalientConceptReference
from authordoc.storydoc import Document


class ExposureTracker:
    """Which references to the story's salient concepts the player was shown: a
    reference is seen when its words overlap the words of a node shown in a scene."""

    def __init__(self, doc: Document) -> None:
        self.concepts = [cell for cell in doc.cells if isinstance(cell, SalientConceptCell)]
        self._seen_reference_ids: set[str] = set()

    def see(self, nodes: Sequence[PlotNode]) -> None:
        for concept in self.concepts:
            for reference in concept.references:
                for node in nodes:
                    if reference.story_word_range.overlaps(node.story_word_range):
                        self._seen_reference_ids.add(reference.reference_id)

    def get_seen_references(self, concept: SalientConceptCell) -> list[SalientConceptReference]:
        seen_references = [
            reference for reference in concept.references if reference.reference_id in self._seen_reference_ids
        ]
        return seen_references

    def get_exposure(self, concept: SalientConceptCell) -> float:
        """The share of the concept's references that were seen; 0 for a concept
        without references."""
        if not concept.references:
            return 0.0
        seen_references = self.get_seen_references(concept)
        exposure = len(seen_references) / len(concept.references)
        return exposure
