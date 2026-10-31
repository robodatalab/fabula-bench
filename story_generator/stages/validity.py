"""Whether the story does what the benchmark needs of it, found by playing it
with the benchmark's own player, with no model: scripted plays, and what they
are shown, as the benchmark's exposure tracker records it. The stage only
reports, in the log: it changes nothing in the story, and asks the author
nothing.

1. Following every plot from start to finish. A play starts at the plot's first
   event, and at every scene takes the choice that leads on to the plot's next
   event. The plot breaks where the play cannot go on: where the player fails to
   show the scene, or the scene offers no choice leading on, or two of its
   choices read the same; or where the play ends without having been shown the
   whole plot, each event right after the one before it.
2. Seeing every reference of every concept. The same play must be shown every
   reference of every concept the plot illustrates; every reference it is not
   shown is reported, by its text.
3. Taking the same option every time. From the first event of every plot, the
   story is played over and over taking option 1 every time, then option 2, and
   so on, ending, as the benchmark's agent player does, at a scene that offers
   fewer options. The player shuffles a scene's choices every time it shows them,
   so the plays differ. Each play's longest consistent trajectory of the plot,
   its events each right after the one before it, is measured as the
   plot-following score measures trajectories: how many plays reach the plot's
   end, and how many have a longest trajectory of each length.
4. Where plots meet. The scenes where plots intersect, against the scenes that
   offer a single choice.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices, get_scene_at
from fabula_bench.metrics.plot_following import get_trajectories
from fabula_bench.story_player.exposure_tracker import ExposureTracker
from fabula_bench.story_player.story_player import StoryPlayer
from story_generator.stage import Stage
from story_generator.stages.plot_ends import get_illustrated
from story_generator.stages.scenes import get_cell_of_event, get_scene_cell, get_scenes

# How many times every plot is played from its start, taking each option every
# time.
PLAYS = 100

# How many words of a reference not shown are reported.
OPENING_WORDS = 12

# What the benchmark's player raises when it cannot show a scene: a choice
# missing for an edge, an event told by no scene, a scene no cell tells.
PLAYER_FAILURES = (KeyError, AttributeError, StopIteration)


@dataclass(frozen=True)
class BreakingPoint:
    """Where a play following a plot to the letter cannot go on."""

    # What happens at the event the play broke at.
    event: str
    reason: str


@dataclass(frozen=True)
class UnseenReferences:
    """The references of a concept that a play following a plot it illustrates
    is not shown."""

    concept: str
    # How many references the concept has.
    total: int
    # The opening words of every reference not shown.
    openings: list[str]


@dataclass(frozen=True)
class SameOption:
    """What the plays that take the same option every time, from the start of a
    plot, were shown of it: how many plays had a longest consistent trajectory of
    the plot of each length. The plays whose trajectory is the plot's whole
    length reached its end."""

    option: int
    # How many plays had a longest consistent trajectory of each length.
    longest_runs: dict[int, int]


@dataclass(frozen=True)
class PlotChecked:
    title: str
    length: int
    # Where following the plot to the letter broke; None where it did not.
    breaking_point: BreakingPoint | None
    unseen: list[UnseenReferences]
    same_options: list[SameOption]


@dataclass(frozen=True)
class SceneCounts:
    scenes: int
    # Scenes where events of more than one plot meet.
    intersections: int
    # Scenes told with a single choice.
    single: int


def get_longest_run(plot: PlotCell, events_seen: list[PlotNode]) -> int:
    """How many events of the plot the play was shown in its longest consistent
    trajectory, as the plot-following score finds trajectories."""
    trajectories = get_trajectories(plot, events_seen)
    lengths = [len(trajectory) for trajectory in trajectories]
    longest = max(lengths, default=0)
    return longest


def play_following(document: Document, plot_index: int) -> tuple[ExposureTracker, BreakingPoint | None]:
    """Plays the story from the first event of the plot at `plot_index`, taking at
    every scene the choice that leads on to the plot's next event. Returns what
    the play was shown, and where it broke, if it did."""
    plots = document.plots()
    plot = plots[plot_index]
    cell_of_event = get_cell_of_event(document)
    edge_from = {edge.from_node_id: edge for edge in plot.edges}
    tracker = ExposureTracker(document)
    player = StoryPlayer(document, tracker, plot_index)
    event = plot.nodes[0]
    for _ in plot.nodes:
        try:
            _, continuations = player.get_current_scene()
        except PLAYER_FAILURES as failure:
            failure_type = type(failure)
            kind = failure_type.__name__
            failed = BreakingPoint(event.summary, f"the player fails to show its scene ({kind}: {failure})")
            return (tracker, failed)
        edge = edge_from.get(event.node_id)
        if edge is None:
            break
        next_event = plot.get_node_by_id(edge.to_node_id)
        cell_id = cell_of_event[event.node_id]
        scene_cell = document.cell_with_id(cell_id)
        choices = get_choices(scene_cell.source)
        choice = choices.get(edge.edge_id)
        if choice is None or choice not in continuations:
            not_offered = BreakingPoint(
                event.summary, f'its scene offers no choice leading on to "{next_event.summary}"'
            )
            return (tracker, not_offered)
        readings = continuations.count(choice)
        if readings > 1:
            alike = BreakingPoint(
                event.summary, f'{readings} of its choices read the same as the one leading on: "{choice}"'
            )
            return (tracker, alike)
        action = continuations.index(choice)
        player.step(action)
        event = next_event
    longest = get_longest_run(plot, tracker.events_seen)
    length = len(plot.nodes)
    if longest < length:
        short = BreakingPoint(
            event.summary, f"the play ends here, shown {longest} of the plot's {length} events in a row"
        )
        return (tracker, short)
    return (tracker, None)


def get_unseen_references(document: Document, plot: PlotCell, tracker: ExposureTracker) -> list[UnseenReferences]:
    """For every concept the plot illustrates, the references the play was not
    shown, as the tracker recorded it; a concept whose references were all shown
    is left out."""
    story_words = StoryWordsIterator(document)
    illustrated = get_illustrated(plot)
    concepts = document.salient_concepts()
    unseen_references = []
    for concept in concepts:
        if concept.title not in illustrated:
            continue
        seen = tracker.get_seen_references(concept)
        seen_ids = {reference.reference_id for reference in seen}
        openings = []
        for reference in concept.references:
            if reference.reference_id in seen_ids:
                continue
            text = story_words.text(reference.story_word_range)
            words = text.split()
            opening = " ".join(words[:OPENING_WORDS])
            cut = "…" if len(words) > OPENING_WORDS else ""
            openings.append(f"{opening}{cut}")
        total = len(concept.references)
        if openings or not total:
            unseen = UnseenReferences(concept.title, total, openings)
            unseen_references.append(unseen)
    return unseen_references


def play_same_option(document: Document, plot_index: int, option: int) -> list[PlotNode]:
    """Plays the story from the first event of the plot at `plot_index`, taking the
    option every time, until a scene offers fewer options or the story ends.
    Returns every event the play was shown, in the order it was shown them."""
    plots = document.plots()
    plot = plots[plot_index]
    tracker = ExposureTracker(document)
    player = StoryPlayer(document, tracker, plot_index)
    # A play that goes round for ever is ended once it has taken as many steps as
    # the story has events.
    event_counts = [len(each.nodes) for each in plots]
    steps = sum(event_counts)
    try:
        _, continuations = player.get_current_scene()
        while option <= len(continuations) and steps:
            player.step(option - 1)
            _, continuations = player.get_current_scene()
            steps -= 1
    except PLAYER_FAILURES:
        # The player cannot show the scene: the play ends there.
        pass
    events_seen = tracker.events_seen
    return events_seen


def get_most_offered(document: Document) -> int:
    """The most choices any scene offers a play."""
    plots = document.plots()
    offered_counts = []
    for plot in plots:
        for event in plot.nodes:
            _, edges = get_scene_at(document, plot, event)
            offered = len(edges)
            offered_counts.append(offered)
    most_offered = max(offered_counts, default=0)
    return most_offered


def get_scene_counts(document: Document) -> SceneCounts:
    """How many scenes the story has, how many of them are where plots intersect,
    and how many offer a single choice."""
    plots = document.plots()
    plot_of_event = {event.node_id: each.unique_id for each in plots for event in each.nodes}
    scenes = get_scenes(document)
    intersections = 0
    single = 0
    for scene in scenes:
        plots_met = {plot_of_event[event.node_id] for event in scene}
        if len(plots_met) > 1:
            intersections += 1
        scene_cell = get_scene_cell(document, scene)
        if scene_cell is None:
            continue
        choices = get_choices(scene_cell.source)
        if len(choices) == 1:
            single += 1
    count = len(scenes)
    counts = SceneCounts(count, intersections, single)
    return counts


def written_report(plots: list[PlotChecked], scenes: SceneCounts) -> list[str]:
    """The report, line by line."""
    lines = []
    broken = [plot for plot in plots if plot.breaking_point is not None]
    if not broken:
        lines.append("plots that cannot be followed from start to finish: none")
    else:
        lines.append("plots that cannot be followed from start to finish:")
        for plot in broken:
            point = plot.breaking_point
            assert point is not None
            lines.append(f'- {plot.title}, breaking at "{point.event}": {point.reason}')
    incomplete = [plot for plot in plots if plot.unseen]
    if not incomplete:
        lines.append("concepts with references a play following their plot is not shown: none")
    else:
        lines.append("concepts with references a play following their plot is not shown:")
        for plot in incomplete:
            for unseen in plot.unseen:
                if not unseen.total:
                    lines.append(f"- {unseen.concept}, following {plot.title}: it has no references")
                    continue
                count = len(unseen.openings)
                lines.append(f"- {unseen.concept}, following {plot.title}: {count} of {unseen.total} not shown:")
                lines.extend(f'  "{opening}"' for opening in unseen.openings)
    lines.append(f"taking the same option every time, from the start of every plot, played {PLAYS} times each:")
    for plot in plots:
        lines.append(f"- {plot.title}, {plot.length} events:")
        for same in plot.same_options:
            reached_end = same.longest_runs.get(plot.length, 0)
            end_achieved = reached_end / PLAYS
            by_length = sorted(same.longest_runs.items())
            runs = []
            for length, plays in by_length:
                events = "event" if length == 1 else "events"
                share = plays / PLAYS
                runs.append(f"{length} {events} {share:.0%}")
            written_runs = ", ".join(runs)
            lines.append(
                f"  always option {same.option} - plot end achieved {end_achieved:.0%}, "
                f"longest consistent plot trajectory: {written_runs}"
            )
    lines.append(
        f"scenes: {scenes.scenes}; intersections, where plots meet: {scenes.intersections}; "
        f"scenes with only 1 choice: {scenes.single}"
    )
    return lines


class Validity(Stage):
    def __init__(self) -> None:
        # What the stage found: every plot, played, and the story's scenes,
        # counted.
        self.plots: list[PlotChecked] = []
        self.scenes = SceneCounts(0, 0, 0)

    def run(self, **params: Any) -> None:
        story: Path = params["story"]
        logger = logging.getLogger(__name__)
        document = Document.load(story)
        plots = document.plots()
        most_offered = get_most_offered(document)
        options = range(1, most_offered + 1)
        count = len(plots)
        self.plots = []
        for plot_index, plot in enumerate(plots):
            logger.info("playing %s (%d of %d)", plot.title, plot_index + 1, count)
            length = len(plot.nodes)
            if not plot.nodes:
                no_events = BreakingPoint("", "the plot has no events")
                empty = PlotChecked(plot.title, 0, no_events, [], [])
                self.plots.append(empty)
                continue
            tracker, breaking_point = play_following(document, plot_index)
            unseen = get_unseen_references(document, plot, tracker)
            same_options = []
            for option in options:
                longest_runs: Counter[int] = Counter()
                for _ in range(PLAYS):
                    events_seen = play_same_option(document, plot_index, option)
                    longest = get_longest_run(plot, events_seen)
                    longest_runs[longest] += 1
                runs = dict(longest_runs)
                same_option = SameOption(option, runs)
                same_options.append(same_option)
            checked = PlotChecked(plot.title, length, breaking_point, unseen, same_options)
            self.plots.append(checked)
        self.scenes = get_scene_counts(document)
        report = written_report(self.plots, self.scenes)
        for line in report:
            logger.info("%s", line)
