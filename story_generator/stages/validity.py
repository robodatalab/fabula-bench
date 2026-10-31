"""Whether the story does what the benchmark needs of it, checked with no model,
by playing it as the benchmark plays it.

Every plot is followed to the letter, from its first event: at every scene, the
play takes the choice that goes on to the plot's next event. It must see the
whole plot, every event right after the one before it, and every passage of every
concept the plot illustrates.

A play that chooses blindly must not follow a plot as well. The benchmark
shuffles a scene's choices every time it shows them, so a play that always takes
the same choice chooses blindly, and follows a plot to its end by the chance of
taking the plot's choice at every scene of it: one in as many as the scene offers.
A plot that chance follows more often than one time in ten is too easy to follow:
following it says little of the play that did.

Across the story, the scenes where plots meet are counted, against those that go
on to a single scene, and those the story ends at.

The author reads the report and accepts the story as it stands, or stops: there
is no draft to revise, and what is to change is changed by going back to the
stage that wrote it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authordoc.cells.plot_cell import PlotCell
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices, get_scene_at
from fabula_bench.metrics.plot_following import score_plot_following
from fabula_bench.story_player.exposure_tracker import ExposureTracker
from story_generator.stage import AuthorStopped, Stage
from story_generator.stage_visitor import Review, StageVisitor, Verdict
from story_generator.stages.plot_ends import get_illustrated
from story_generator.stages.scenes import get_cell_of_event, get_scene_cell, get_scenes

# The most chance there may be that a play choosing blindly follows a plot to its
# end.
MOST_LUCK = 0.1


@dataclass(frozen=True)
class PlotFollowed:
    """What a play that follows a plot to the letter is shown."""

    title: str
    # How closely the play followed the plot: 1 when it saw every event of it,
    # each right after the one before it.
    following: float
    # Why the play could not go on along the plot; none when it went to the end.
    breaks: list[str]
    # The share of every illustrated concept's passages the play saw, by the
    # concept's title.
    exposures: dict[str, float]
    # The chance that a play choosing blindly follows the plot to its end.
    luck: float


@dataclass(frozen=True)
class SceneCounts:
    """How the story's scenes go on."""

    scenes: int
    # Scenes where events of more than one plot meet.
    meetings: int
    # Scenes that go on to a single scene: told with one choice.
    single: int
    # Scenes the story ends at: told with no choice.
    endings: int
    # Scenes no cell tells.
    untold: int


def get_followed(document: Document, plot: PlotCell) -> PlotFollowed:
    """What a play that follows the plot to the letter, from its first event, is
    shown, scene by scene, as the benchmark plays it."""
    if not plot.nodes:
        empty = PlotFollowed(plot.title, 0.0, ["it has no events"], {}, 1.0)
        return empty
    tracker = ExposureTracker(document)
    cell_of_event = get_cell_of_event(document)
    edge_from = {edge.from_node_id: edge for edge in plot.edges}
    breaks: list[str] = []
    luck = 1.0
    passed: set[str] = set()
    event = plot.nodes[0]
    while event.node_id not in passed:
        passed.add(event.node_id)
        nodes, edges = get_scene_at(document, plot, event)
        untold = [node.summary for node in nodes if node.node_id not in cell_of_event]
        if untold:
            listed = "; ".join(untold)
            breaks.append(f"no scene tells {listed}")
            break
        tracker.see(nodes)
        edge = edge_from.get(event.node_id)
        if edge is None:
            break
        cell_id = cell_of_event[event.node_id]
        scene_cell = document.cell_with_id(cell_id)
        choices = get_choices(scene_cell.source)
        unchosen = [leaving for leaving in edges if leaving.edge_id not in choices]
        if unchosen:
            count = len(unchosen)
            breaks.append(f'the scene of "{event.summary}" has no choice for {count} of the edges leaving it')
            break
        offered = len(edges)
        luck = luck / offered
        event = plot.get_node_by_id(edge.to_node_id)
    following = score_plot_following(plot, tracker.events_seen)
    concepts = document.salient_concepts()
    illustrated = get_illustrated(plot)
    exposures = {
        concept.title: tracker.get_exposure(concept) for concept in concepts if concept.title in illustrated
    }
    followed = PlotFollowed(plot.title, following, breaks, exposures, luck)
    return followed


def get_scene_counts(document: Document) -> SceneCounts:
    """How the story's scenes go on: where plots meet, and how many scenes each
    goes on to."""
    plots = document.plots()
    plot_of_event = {event.node_id: plot.unique_id for plot in plots for event in plot.nodes}
    scenes = get_scenes(document)
    meetings = 0
    single = 0
    endings = 0
    untold = 0
    for scene in scenes:
        plots_met = {plot_of_event[event.node_id] for event in scene}
        if len(plots_met) > 1:
            meetings += 1
        scene_cell = get_scene_cell(document, scene)
        if scene_cell is None:
            untold += 1
            continue
        choices = get_choices(scene_cell.source)
        if len(choices) == 1:
            single += 1
        elif not choices:
            endings += 1
    count = len(scenes)
    counts = SceneCounts(count, meetings, single, endings, untold)
    return counts


def written_report(plots: Sequence[PlotFollowed], scenes: SceneCounts) -> str:
    """What the author reads: every plot as a play following it to the letter is
    shown it, and how the story's scenes go on."""
    most_odds = round(1 / MOST_LUCK)
    lines = ["Every plot, followed to the letter from its first event:"]
    for followed in plots:
        whole = followed.following == 1.0 and not followed.breaks
        seen = "seen whole" if whole else f"not seen whole, followed at {followed.following:.2f}"
        lines.append(f"- {followed.title}: {seen}")
        lines.extend(f"  breaks off: {written_break}" for written_break in followed.breaks)
        passages = [f"{title} {exposure:.0%}" for title, exposure in followed.exposures.items()]
        written_passages = ", ".join(passages) or "none: it illustrates no concept"
        lines.append(f"  passages seen: {written_passages}")
        odds = round(1 / followed.luck)
        too_easy = f": too easy, above 1 in {most_odds}" if followed.luck > MOST_LUCK else ""
        lines.append(f"  a play choosing blindly follows it to its end 1 time in {odds}{too_easy}")
    lines.append("")
    lines.append(
        f"Scenes: {scenes.scenes}; where plots meet: {scenes.meetings}; "
        f"going on to a single scene: {scenes.single}; ending the story: {scenes.endings}"
    )
    if scenes.untold:
        lines.append(f"Scenes no cell tells: {scenes.untold}")
    report = "\n".join(lines)
    return report


class Validity(Stage):
    def __init__(self) -> None:
        super().__init__()
        # What the renderer shows beside the report: every plot as a play
        # following it to the letter is shown it, and how the story's scenes go on.
        self.plots: list[PlotFollowed] = []
        self.scenes = SceneCounts(0, 0, 0, 0, 0)

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        renderer: StageVisitor = params["renderer"]
        document = Document.load(story)
        plots = document.plots()
        self.plots = [get_followed(document, plot) for plot in plots]
        self.scenes = get_scene_counts(document)
        self.draft = written_report(self.plots, self.scenes)
        self.progress = (0, 1)
        review = self.accept(renderer)
        if review.verdict is not Verdict.ACCEPT:
            raise AuthorStopped
        self.progress = (1, 1)

    def accept(self, visitor: StageVisitor) -> Review:
        review = visitor.visit_validity(self)
        return review
