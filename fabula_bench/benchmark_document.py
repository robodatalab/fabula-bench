"""What the benchmark reads from an `.author` document beyond its storydoc format.

Every low-level plot event has a timestamp and a location: the timestamp is a
clock shared by all the plots, and the location runs from the broadest place to
the most specific, as in "earth, Varn's house". Events at the same moment, in
places one of which contains the other, form one scene.
"""

from fabula_bench.storydoc.cells.plot_cell import PlotNode


def get_tag(node: PlotNode) -> tuple[str, list[str]] | None:
    """The moment and the place of the node's event; None for an event without
    them."""
    if node.timestamp == "" or node.location == "":
        return None
    place_parts = node.location.split(",")
    place = [part.strip() for part in place_parts]
    return (node.timestamp, place)


def tags_meet(tag: tuple[str, list[str]] | None, other_tag: tuple[str, list[str]] | None) -> bool:
    """Whether the two events form one scene."""
    if tag is None or other_tag is None:
        return False
    time, place = tag
    other_time, other_place = other_tag
    shared_depth = min(len(place), len(other_place))
    return time == other_time and place[:shared_depth] == other_place[:shared_depth]


def get_place(nodes: list[PlotNode]) -> str:
    """Where the scene made of these nodes takes place: the nodes meet where the
    most specific of their places is."""
    tags = [get_tag(node) for node in nodes]
    places = [tag[1] for tag in tags if tag is not None]
    place = max(places, key=len)
    where = ", ".join(place)
    return where
