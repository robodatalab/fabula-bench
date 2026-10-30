import unittest

from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode

from fabula_bench.metrics.plot_following import get_trajectories


def _plot(title: str, count: int) -> PlotCell:
    """A plot of `count` events, each caused by the one before it."""
    events = [PlotNode(f"{title}{number}", None) for number in range(1, count + 1)]
    edges = [
        PlotEdge(f"{cause.node_id}-{effect.node_id}", cause.node_id, effect.node_id)
        for cause, effect in zip(events, events[1:])
    ]
    plot = PlotCell(title=title, nodes=events, edges=edges)
    return plot


P = _plot("E", 10)
E_1, E_2, E_3, E_4, E_5, E_6, E_7, E_8, E_9, E_10 = P.nodes
Q = _plot("F", 3)
F_1, F_2, F_3 = Q.nodes


class Trajectories(unittest.TestCase):
    def test_are_one_for_a_plot_seen_from_its_first_event_to_its_last(self) -> None:
        trajectories = get_trajectories([P], P.nodes)

        self.assertEqual(trajectories, [[P.nodes]])

    def test_break_at_every_skipped_event_and_every_step_back(self) -> None:
        trajectories = get_trajectories([P], [E_3, E_4, E_8, E_6, E_9, E_10])

        self.assertEqual(trajectories, [[[E_3, E_4], [E_8], [E_6], [E_9, E_10]]])

    def test_carry_on_through_the_events_of_other_plots(self) -> None:
        trajectories = get_trajectories([P, Q], [E_1, F_1, E_2, F_2])

        self.assertEqual(trajectories, [[[E_1, E_2]], [[F_1, F_2]]])

    def test_are_none_for_a_plot_never_seen(self) -> None:
        trajectories = get_trajectories([P, Q], [F_1])

        self.assertEqual(trajectories, [[], [[F_1]]])
