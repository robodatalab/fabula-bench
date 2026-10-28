"""The scenes a document's plots make: its events grouped by where and when they
happen."""

from __future__ import annotations

from fabula_bench.benchmark_document import get_tag, tags_meet
from fabula_bench.storydoc.cells.plot_cell import PlotNode
from fabula_bench.storydoc.storydoc import Document


def scenes_of(document: Document) -> list[list[PlotNode]]:
    """Every event with a timestamp and a location, grouped with every event it
    meets — at the same moment, in places one of which contains the other — in
    the order of the clock, and within a scene in the order the plots give them.
    An event without a timestamp or a location is in no scene."""
    scenes: list[list[PlotNode]] = []
    for plot in document.plots():
        for event in plot.nodes:
            tag = get_tag(event)
            if tag is None:
                continue
            scenes_met = [
                scene
                for scene in scenes
                if any(tags_meet(get_tag(event_met), tag) for event_met in scene)
            ]
            scene_joined = [event_met for scene in scenes_met for event_met in scene]
            scenes = [scene for scene in scenes if scene not in scenes_met]
            scenes.append([*scene_joined, event])
    scenes.sort(key=_when)
    return scenes


def _when(scene: list[PlotNode]) -> tuple[int, tuple[int, ...], str]:
    """Where a scene stands on the clock: a timestamp of numbers, like "3.1", by
    its numbers; any other after all of those, by its text."""
    timestamp = scene[0].timestamp
    parts = timestamp.split(".")
    if all(part.isdigit() for part in parts):
        numbers = tuple(int(part) for part in parts)
        return (0, numbers, "")
    return (1, (), timestamp)
