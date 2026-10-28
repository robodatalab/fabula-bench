"""What the benchmark reads from an `.author` document beyond its storydoc format.

Every low-level plot event begins with its moment and its place, as in
"1.1. [earth, Varn's house] ...": the moment is a clock shared by all the plots,
and the place runs from the broadest to the most specific. Events at the same
moment, in places one of which contains the other, form one scene.
"""

import re

from fabula_bench.storydoc.cells.plot_cell import PlotNode
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document

# "1.1. [earth, Varn's house] ..." - the time and the place of an event
_TAG = re.compile(r"^(\d+\.\d+)\. \[([^\]]*)\]")


def get_tag(node: PlotNode, story_text: StoryWordsIterator) -> tuple[str, list[str]] | None:
    """The moment and the place of the node's event; None for a node whose words
    do not begin with them."""
    node_text = story_text.text(node.story_word_range)
    tag = _TAG.match(node_text)
    if tag is None:
        return None
    time = tag.group(1)
    written_place = tag.group(2)
    place_parts = written_place.split(",")
    place = [part.strip() for part in place_parts]
    return (time, place)


def tags_meet(tag: tuple[str, list[str]] | None, other_tag: tuple[str, list[str]] | None) -> bool:
    """Whether the two events form one scene."""
    if tag is None or other_tag is None:
        return False
    time, place = tag
    other_time, other_place = other_tag
    shared_depth = min(len(place), len(other_place))
    return time == other_time and place[:shared_depth] == other_place[:shared_depth]


def get_place(document: Document, nodes: list[PlotNode]) -> str:
    """Where the scene made of these nodes takes place: the nodes meet where the
    most specific of their places is."""
    story_text = StoryWordsIterator(document)
    tags = [get_tag(node, story_text) for node in nodes]
    places = [tag[1] for tag in tags if tag is not None]
    place = max(places, key=len)
    where = ", ".join(place)
    return where
