import re

from fabula_bench.storydoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document

# "1.1. [earth, Varn's house] ..." - the time and the place of an event
_TAG = re.compile(r"^(\d+\.\d+)\. \[([^\]]*)\]")


class StoryPlayer:

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._plots = [cell for cell in doc.cells if isinstance(cell, PlotCell)]
        self.followed_plot = self._plots[1]
        self._current_node = self.followed_plot.nodes[0]

    def get_current_scene(self) -> tuple[list[PlotNode], list[PlotEdge], bool]:
        story_text = StoryWordsIterator(self._doc)
        current_tag = self.get_tag(self._current_node, story_text)
        current_nodes = [self._current_node]
        outgoing_edges = [
            edge for edge in self.followed_plot.edges if edge.from_node_id == self._current_node.node_id
        ]
        for plot in self._plots:
            if plot is self.followed_plot:
                continue
            for node in plot.nodes:
                tag = self.get_tag(node, story_text)
                if self.tags_meet(tag, current_tag):
                    current_nodes.append(node)
                    outgoing_edges += [edge for edge in plot.edges if edge.from_node_id == node.node_id]
        finished = not outgoing_edges
        return (current_nodes, outgoing_edges, finished)

    def get_tag(self, node: PlotNode, story_text: StoryWordsIterator) -> tuple[str, list[str]] | None:
        node_text = story_text.text(node.story_word_range)
        tag = _TAG.match(node_text)
        if tag is None:
            return None
        time = tag.group(1)
        written_place = tag.group(2)
        place_parts = written_place.split(",")
        place = [part.strip() for part in place_parts]
        return (time, place)

    def tags_meet(self, tag: tuple[str, list[str]] | None, other_tag: tuple[str, list[str]] | None) -> bool:
        if tag is None or other_tag is None:
            return False
        time, place = tag
        other_time, other_place = other_tag
        shared_depth = min(len(place), len(other_place))
        return time == other_time and place[:shared_depth] == other_place[:shared_depth]

    def get_plot_of_edge(self, edge: PlotEdge) -> PlotCell:
        plot = next(plot for plot in self._plots if edge in plot.edges)
        return plot

    def step(self, edge: PlotEdge) -> None:
        self.followed_plot = self.get_plot_of_edge(edge)
        self._current_node = self.followed_plot.get_node_by_id(edge.to_node_id)
