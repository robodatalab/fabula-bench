"""The story written into a document: one markdown cell for every scene, appended
after the document's cells, and every event of a scene pointed at its words; then
the choices every scene the story goes on from ends with."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from authordoc.cells.cell import Cell
from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell, SalientConceptReference
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import written_scene
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


def with_the_choices(
    document: Document,
    scene_writer: SceneWriter,
    on_scene_written: Callable[[int, int], None] = lambda written, scenes: None,
) -> Document:
    """The document with the choices written at the end of every scene it tells
    that the story goes on from: one for each edge leaving the scene's events.
    The choices only follow words the document had, so every event and every
    salient concept is pointed at the same words as before."""
    scenes = scenes_of(document)
    words = StoryWordsIterator(document)
    cell_of_each_word = {word.number: word.cell_id for word in words}
    sources_with_choices: dict[str, str] = {}
    for scenes_written, scene in enumerate(scenes, start=1):
        edges, next_events = _leaving(document, scene)
        scene_words = scene[0].story_word_range
        if edges and scene_words is not None:
            scene_cell_id = cell_of_each_word[scene_words.first_word]
            scene_cell = document.cell_with_id(scene_cell_id)
            opening, endings = scene_writer.write_choices(scene_cell.source, next_events)
            choices = {edge.edge_id: ending for edge, ending in zip(edges, endings, strict=True)}
            source_with_choices = written_scene(scene_cell.source, opening, choices)
            sources_with_choices[scene_cell_id] = source_with_choices
        on_scene_written(scenes_written, len(scenes))
    cells_with_choices: list[Cell] = []
    for cell in document.cells:
        source_with_choices = sources_with_choices.get(cell.unique_id)
        if source_with_choices is None:
            cells_with_choices.append(cell)
        else:
            cell_with_choices = cell.with_source(source_with_choices)
            cells_with_choices.append(cell_with_choices)
    with_choices = Document.from_cells(cells_with_choices, document.path)
    story = _pointed_at_the_same_words(with_choices, document)
    return story


def _pointed_at_the_same_words(document: Document, before: Document) -> Document:
    """The document with every event and every salient concept pointed at the
    words they were pointed at in `before`, whose every word it has, at the same
    place in the same cell."""
    numbers_now = {
        (word.cell_id, word.start_character_offset_in_cell): word.number
        for word in StoryWordsIterator(document)
    }
    number_now = {
        word.number: numbers_now[(word.cell_id, word.start_character_offset_in_cell)]
        for word in StoryWordsIterator(before)
    }
    cells_pointed: list[Cell] = []
    for cell in document.cells:
        if isinstance(cell, PlotCell):
            nodes = [_node_moved(node, number_now) for node in cell.nodes]
            cell_pointed = replace(cell, nodes=nodes)
            cells_pointed.append(cell_pointed)
        elif isinstance(cell, SalientConceptCell):
            references = [_reference_moved(reference, number_now) for reference in cell.references]
            cell_pointed = replace(cell, references=references)
            cells_pointed.append(cell_pointed)
        else:
            cells_pointed.append(cell)
    story = Document.from_cells(cells_pointed, document.path)
    return story


def _leaving(document: Document, scene: list[PlotNode]) -> tuple[list[PlotEdge], list[PlotNode]]:
    """The edges leaving the scene's events, in the order of the plots, and the
    event each of them leads to."""
    scene_event_ids = {event.node_id for event in scene}
    edges: list[PlotEdge] = []
    next_events: list[PlotNode] = []
    for plot in document.plots():
        for edge in plot.edges:
            if edge.from_node_id in scene_event_ids:
                next_event = plot.get_node_by_id(edge.to_node_id)
                edges.append(edge)
                next_events.append(next_event)
    return (edges, next_events)


def _node_moved(node: PlotNode, number_now: dict[int, int]) -> PlotNode:
    if node.story_word_range is None:
        return node
    words = _words_moved(node.story_word_range, number_now)
    node_moved = replace(node, story_word_range=words)
    return node_moved


def _reference_moved(reference: SalientConceptReference, number_now: dict[int, int]) -> SalientConceptReference:
    words = _words_moved(reference.story_word_range, number_now)
    reference_moved = replace(reference, story_word_range=words)
    return reference_moved


def _words_moved(words: StoryWordRange, number_now: dict[int, int]) -> StoryWordRange:
    first_word = number_now[words.first_word]
    last_word = number_now[words.last_word]
    words_moved = StoryWordRange(first_word, last_word)
    return words_moved


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
