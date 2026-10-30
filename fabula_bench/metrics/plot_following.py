"""How a play followed the story's plots: every trajectory along which it followed
each plot.

A plot is a sequence of events in causal order. A trajectory is a run of a
plot's events the play saw, each the very next event after the one before it:
the event the plot's edge from it leads to. Seeing a plot's event that is not
the very next one, whether it skips events or steps back, ends the trajectory
and starts another at that event. Seeing other plots' events in between ends
nothing.
"""

from __future__ import annotations

from collections.abc import Sequence

from authordoc.cells.plot_cell import PlotCell, PlotNode


def get_trajectories(plots: Sequence[PlotCell], exposure: Sequence[PlotNode]) -> list[list[list[PlotNode]]]:
    """Every trajectory along which the play followed each plot, given every event
    it saw, in the order it saw them: for each plot, in the order of the plots,
    its trajectories, in the order they were followed; none for a plot it never
    saw."""
    trajectories_of_plots: list[list[list[PlotNode]]] = []
    for plot in plots:
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
        trajectories_of_plots.append(trajectories)
    return trajectories_of_plots
