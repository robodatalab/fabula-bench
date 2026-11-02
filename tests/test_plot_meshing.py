import unittest
from itertools import combinations

from story_generator.stages.mesh import build_round_robin_plot_matrix, matrix_to_connectivity_trajectory


class PlotMeshingTest(unittest.TestCase):

    def test_matrix_to_unique_tuples(self):
        self.assertSequenceEqual(
            matrix_to_connectivity_trajectory([[0, 1, 2], [1, 2, 0], [2, 0, 1]]),
            [
                set(),
                {(0, 1), (1, 2), (0, 2)},
                {(0, 2), (0, 1), (1, 2)},
            ],
        )

        self.assertSequenceEqual(
            matrix_to_connectivity_trajectory([[1, 2], [3, 1], [2, 3], [1, 0]]),
            [
                {(0, 1), (1, 3)},
                {(0, 2), (2, 3), (0, 3)},
            ],
        )

    def test_each_plot_meets_each_other_plot_often_and_evenly(self):
        # P plots, trajectories of T > P events: every pair of plots meets at
        # least once, and at least T / P times, rounded down when T / P falls
        # between two integers, and the gaps between its consecutive meetings
        # differ by at most 1 event.
        for n_plots in range(2, 7):
            for traj_len in range(n_plots + 1, 21):
                matrix = build_round_robin_plot_matrix(n_plots, traj_len)
                trajectory = matrix_to_connectivity_trajectory(matrix)
                plot_indices = range(n_plots)
                pairs = combinations(plot_indices, 2)
                for pair in pairs:
                    with self.subTest(n_plots=n_plots, traj_len=traj_len, pair=pair):
                        meetings = [event_idx for event_idx, merges in enumerate(trajectory) if pair in merges]
                        n_meetings = len(meetings)
                        self.assertGreaterEqual(n_meetings, 1)
                        self.assertGreaterEqual(n_meetings, traj_len // n_plots)
                        gaps = [later - earlier for earlier, later in zip(meetings, meetings[1:])]
                        # A pair that meets once has no gaps to compare.
                        if not gaps:
                            continue
                        longest_gap = max(gaps)
                        shortest_gap = min(gaps)
                        gap_spread = longest_gap - shortest_gap
                        self.assertLessEqual(gap_spread, 1)

