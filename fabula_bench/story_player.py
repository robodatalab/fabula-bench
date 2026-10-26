from pathlib import Path

from fabula_bench.storydoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document


class StoryPlayer:

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._plots = [cell for cell in doc.cells if isinstance(cell, PlotCell)]
        self.followed_plot = self._plots[1]
        self._current_node = self.followed_plot.nodes[0]

    def get_current_scene(self) -> tuple[list[PlotNode], list[PlotEdge], bool]:
        current_nodes = [self._current_node]
        outgoing_edges = [
            edge for edge in self.followed_plot.edges if edge.from_node_id == self._current_node.node_id
        ]
        for plot in self._plots:
            if plot is self.followed_plot:
                continue
            for node in plot.nodes:
                if node.story_word_range.overlaps(self._current_node.story_word_range):
                    current_nodes.append(node)
                    outgoing_edges += [edge for edge in plot.edges if edge.from_node_id == node.node_id]
        finished = not outgoing_edges
        return (current_nodes, outgoing_edges, finished)

    def get_plot_of_edge(self, edge: PlotEdge) -> PlotCell:
        plot = next(plot for plot in self._plots if edge in plot.edges)
        return plot

    def step(self, edge: PlotEdge) -> None:
        self.followed_plot = self.get_plot_of_edge(edge)
        self._current_node = self.followed_plot.get_node_by_id(edge.to_node_id)


def main() -> None:
    story = Document.load(Path("fabula_bench/stories/hostage.author"))
    player = StoryPlayer(story)
    story_text = StoryWordsIterator(story)

    while True:
        current_nodes, outgoing_edges, finished = player.get_current_scene()
        if finished:
            break
        for current_node in current_nodes:
            current_text = story_text.text(current_node.story_word_range)
            print(f"Current node: {current_text}\n")
        for edge_idx, edge in enumerate(outgoing_edges):
            edge_plot = player.get_plot_of_edge(edge)
            next_node = edge_plot.get_node_by_id(edge.to_node_id)
            next_text = story_text.text(next_node.story_word_range)
            print(f"  {edge_idx}: {next_text}")

        edge_idx = -1
        try:
            edge_idx = int(input("which edge: "))
        except Exception:
            break

        selected_edge = outgoing_edges[edge_idx]
        player.step(selected_edge)


if __name__ == "__main__":
    main()
