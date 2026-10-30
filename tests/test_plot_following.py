import unittest

from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode

from fabula_bench.metrics.plot_following import score_plot_following


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


class ScorePlotFollowing(unittest.TestCase):
    def test_is_one_for_a_plot_followed_from_its_first_event_to_its_last(self) -> None:
        following = score_plot_following(P, P.nodes)

        self.assertEqual(following, 1.0)

    def test_breaks_a_trajectory_at_every_skipped_event_and_every_step_back(self) -> None:
        # The trajectories: [E_3, E_4], [E_8], [E_6] and [E_9, E_10].
        following = score_plot_following(P, [E_3, E_4, E_8, E_6, E_9, E_10])

        self.assertEqual(following, (2**2 + 1**2 + 1**2 + 2**2) / 10**2)

    def test_carries_a_trajectory_on_through_the_events_of_other_plots(self) -> None:
        # The trajectory: [E_1, E_2].
        following = score_plot_following(P, [E_1, F_1, E_2, F_2])

        self.assertEqual(following, 2**2 / 10**2)

    def test_is_zero_for_a_plot_never_seen(self) -> None:
        following = score_plot_following(P, [F_1, F_2, F_3])

        self.assertEqual(following, 0.0)
