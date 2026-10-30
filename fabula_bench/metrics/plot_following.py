"""How closely a play followed a plot.

A plot is a sequence of events in causal order. A trajectory is a run of the
plot's events the play saw, each the very next event after the one before it:
the event the plot's edge from it leads to. Seeing one of the plot's events that
is not the very next one, whether it skips events or steps back, ends the
trajectory and starts another at that event. Seeing other plots' events in
between ends nothing.

The following is the sum of the trajectories' lengths squared, over the plot's
length squared: 1 for a play that followed the plot from its first event to its
last without a break, less the more often it broke off, 0 for a play that never
saw it. Every return to the plot adds to it, by how long the play stayed after
returning.
"""

from __future__ import annotations

from collections.abc import Sequence

from authordoc.cells.plot_cell import PlotCell, PlotNode


def score_plot_following(plot: PlotCell, exposure: Sequence[PlotNode]) -> float:
    """How closely the play followed the plot, given every event it saw, of any
    plot, in the order it saw them."""
    trajectories = _get_trajectories(plot, exposure)
    squared_lengths = [len(trajectory) ** 2 for trajectory in trajectories]
    squared_lengths_sum = sum(squared_lengths)
    event_count = len(plot.nodes)
    following = squared_lengths_sum / event_count**2
    return following


def _get_trajectories(plot: PlotCell, exposure: Sequence[PlotNode]) -> list[list[PlotNode]]:
    """Every trajectory along which the play followed the plot, in the order it
    followed them."""
    event_ids = {event.node_id for event in plot.nodes}
    next_event_ids = {edge.from_node_id: edge.to_node_id for edge in plot.edges}
    trajectories: list[list[PlotNode]] = []
    for event in exposure:
        if event.node_id not in event_ids:
            continue
        if trajectories:
            trajectory = trajectories[-1]
            last = trajectory[-1]
            next_event_id = next_event_ids.get(last.node_id)
            if event.node_id == next_event_id:
                trajectory.append(event)
                continue
        trajectories.append([event])
    return trajectories
