from __future__ import annotations

from dataclasses import dataclass

from fabula_bench.storydoc.cells.about_cell import AboutCell
from fabula_bench.storydoc.cells.blurb_cell import BlurbCell
from fabula_bench.storydoc.cells.cell_visitor import CellVisitor
from fabula_bench.storydoc.cells.chapter_cell import ChapterCell
from fabula_bench.storydoc.cells.disclaimer_cell import DisclaimerCell
from fabula_bench.storydoc.cells.divider_cell import DividerCell
from fabula_bench.storydoc.cells.image_cell import ImageCell
from fabula_bench.storydoc.cells.markdown_cell import MarkdownCell
from fabula_bench.storydoc.cells.note_cell import NoteCell
from fabula_bench.storydoc.cells.part_cell import PartCell
from fabula_bench.storydoc.cells.plot_cell import PlotCell
from fabula_bench.storydoc.cells.recap_cell import RecapCell
from fabula_bench.storydoc.cells.salient_concept_cell import SalientConceptCell
from fabula_bench.storydoc.cells.story_word_range import StoryWordRange
from fabula_bench.storydoc.cells.table_of_contents_cell import TableOfContentsCell
from fabula_bench.storydoc.cells.title_page_cell import TitlePageCell
from fabula_bench.storydoc.cells.unknown_cell import UnknownCell


@dataclass(frozen=True)
class AnnotatedPassages:
    title: str
    story_word_ranges: list[StoryWordRange]


class AnnotatedPassagesOf(CellVisitor["AnnotatedPassages | None"]):
    def visit_salient_concept(self, cell: SalientConceptCell) -> AnnotatedPassages:
        return AnnotatedPassages(cell.title, cell.story_word_ranges)

    def visit_plot(self, cell: PlotCell) -> AnnotatedPassages:
        story_word_ranges = [node.story_word_range for node in cell.nodes]
        return AnnotatedPassages(cell.title, story_word_ranges)

    def visit_markdown(self, cell: MarkdownCell) -> None:
        return None

    def visit_chapter(self, cell: ChapterCell) -> None:
        return None

    def visit_part(self, cell: PartCell) -> None:
        return None

    def visit_divider(self, cell: DividerCell) -> None:
        return None

    def visit_title_page(self, cell: TitlePageCell) -> None:
        return None

    def visit_image(self, cell: ImageCell) -> None:
        return None

    def visit_table_of_contents(self, cell: TableOfContentsCell) -> None:
        return None

    def visit_disclaimer(self, cell: DisclaimerCell) -> None:
        return None

    def visit_about(self, cell: AboutCell) -> None:
        return None

    def visit_blurb(self, cell: BlurbCell) -> None:
        return None

    def visit_note(self, cell: NoteCell) -> None:
        return None

    def visit_recap(self, cell: RecapCell) -> None:
        return None

    def visit_unknown(self, cell: UnknownCell) -> None:
        return None
