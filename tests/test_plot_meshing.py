import unittest


from story_generator.stages.mesh import build_round_robin_plot_matrix


def build_list_of_plot_events_to_merge(d: Document) -> list[list[PlotEvent]]:
    return []
    

class PlotMeshingTest(unittest.TestCase):

    def test_meshing_guarantees_plots_meet_every_n_plots_steps(self):
        self.assertSequenceEqual(build_round_robin_plot_matrix(1, 1), [[0]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(1, 2), [[0, 0]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(1, 3), [[0, 0, 0]])

        self.assertSequenceEqual(build_round_robin_plot_matrix(2, 1), [[0], [1]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(2, 2), [[0, 1], [1, 0]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(2, 3), [[0, 1, 0], [1, 0, 1]])

        self.assertSequenceEqual(build_round_robin_plot_matrix(3, 1), [[0], [1], [2]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(3, 2), [[0, 1], [1, 2], [2, 0]])
        self.assertSequenceEqual(build_round_robin_plot_matrix(3, 3), [[0, 1, 2], [1, 2, 0], [2, 0, 1]])

    def test_iterating_plots_using_meshing_matrix(self):
        d = Document()
        d.add_cell(PlotCell("plot 1", events=[PlotEvent(), PlotEvent(), PlotEvent()]))
        d.add_cell(PlotCell("plot 2", events=[PlotEvent(), PlotEvent(), PlotEvent()]))

        plot_1_events = d.plots[0].events
        plot_2_events = d.plots[1].events
        matrix = [[0, 1], [1, 0]]

        events_to_merge = build_list_of_plot_events_to_merge(d, matrix)

        self.assertSequenceEqual(events_to_merge, [
            [plot_1_events[1], plot_2_events[1]],
        ])
