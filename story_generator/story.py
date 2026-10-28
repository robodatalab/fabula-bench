"""The story written into a document: one markdown cell for every scene, appended
after the document's cells, and every event of a scene pointed at its words."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from fabula_bench.storydoc.cells.cell import Cell
from fabula_bench.storydoc.cells.markdown_cell import MarkdownCell
from fabula_bench.storydoc.cells.plot_cell import PlotCell, PlotNode
from fabula_bench.storydoc.cells.story_word_range import StoryWordRange
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document
from story_generator.scene_writer import SceneWriter
from story_generator.scenes import scenes_of


def with_the_story(
    document: Document,
    scene_writer: SceneWriter,
    on_scene_written: Callable[[int, int], None] = lambda written, scenes: None,
) -> Document:
    """The document with a scene written for every group of its events that
    meet. The scenes come after every cell it has, so no word it has moves."""
    scenes = scenes_of(document)
    scene_cells: list[MarkdownCell] = []
    for scene in scenes:
        prose = scene_writer.write(scene)
        scene_cell = MarkdownCell(source=prose)
        scene_cells.append(scene_cell)
        on_scene_written(len(scene_cells), len(scenes))
    cells_with_the_scenes = [*document.cells, *scene_cells]
    with_the_scenes = Document.from_cells(cells_with_the_scenes, document.path)

    words_of_each_scene = _words_of_each_cell(with_the_scenes)
    words_of_each_event: dict[str, StoryWordRange] = {}
    for scene, scene_cell in zip(scenes, scene_cells, strict=True):
        for event in scene:
            words_of_each_event[event.node_id] = words_of_each_scene[scene_cell.unique_id]
    cells_told: list[Cell] = []
    for cell in with_the_scenes.cells:
        if isinstance(cell, PlotCell):
            nodes = [_told_by(node, words_of_each_event) for node in cell.nodes]
            cell_told = replace(cell, nodes=nodes)
            cells_told.append(cell_told)
        else:
            cells_told.append(cell)
    story = Document.from_cells(cells_told, document.path)
    return story


def _words_of_each_cell(document: Document) -> dict[str, StoryWordRange]:
    numbers_of_each_cell: dict[str, list[int]] = {}
    for word in StoryWordsIterator(document):
        numbers_of_each_cell.setdefault(word.cell_id, []).append(word.number)
    words_of_each_cell = {
        cell_id: StoryWordRange(numbers[0], numbers[-1])
        for cell_id, numbers in numbers_of_each_cell.items()
    }
    return words_of_each_cell


def _told_by(node: PlotNode, words_of_each_event: dict[str, StoryWordRange]) -> PlotNode:
    words = words_of_each_event.get(node.node_id)
    if words is None:
        return node
    node_told = replace(node, story_word_range=words)
    return node_told
