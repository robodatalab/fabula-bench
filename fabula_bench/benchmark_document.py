"""What the benchmark reads from an `.author` document beyond its storydoc format.

Every low-level plot event has a timestamp and a location: the timestamp is a
clock shared by all the plots, and the location runs from the broadest place to
the most specific, as in "earth, Varn's house". Events at the same moment, in
places one of which contains the other, form one scene.

Every scene is told by a markdown cell, which every event of the scene points at.
A scene that the story goes on from ends with the opening of a sentence, left
unfinished, and the choices that finish it, one for each edge leaving the scene's
events, written as a list that names the edge each choice follows:

    Varn's fingers tapped against her knee, _____

    <ol title="choices">
    <li edge="x1">as her phone rang with a call from mission control.</li>
    <li edge="x2">as she watched the gripper close on the object.</li>
    </ol>
"""

import re

from authordoc.cells.plot_cell import PlotNode
from authordoc.written_attributes import attributes_in, written_attribute_value

# Marks the gap the choices fill, at the end of the sentence a scene leaves unfinished.
GAP = "_____"

_ATTRIBUTES = r'((?:\s+[A-Za-z0-9][A-Za-z0-9_-]*\s*=\s*"(?:[^"\\]|\\.)*")*)\s*'
_CHOICES_OPENED = '<ol title="choices">'
_CHOICE = re.compile(rf"^<li{_ATTRIBUTES}>(.*)</li>$")
_CHOICES_CLOSED = "</ol>"
_EDGE = "edge"


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


def written_scene(prose: str, opening: str, choices: dict[str, str]) -> str:
    """A scene's markdown cell as the schema writes it: its prose, the opening of
    the sentence it leaves unfinished, and its choices, each by the id of the edge
    it follows. A scene without choices is its prose alone."""
    if not choices:
        return prose
    written_choices = [
        f'<li {_EDGE}="{written_attribute_value(edge_id)}">{choice}</li>' for edge_id, choice in choices.items()
    ]
    choices_list = "\n".join([_CHOICES_OPENED, *written_choices, _CHOICES_CLOSED])
    return f"{prose}\n\n{opening} {GAP}\n\n{choices_list}"


def get_scene_text(source: str) -> str:
    """What a scene's markdown cell tells, up to the gap its choices fill."""
    scene_text, _, _ = source.partition(_CHOICES_OPENED)
    return scene_text.strip()


def get_choices(source: str) -> dict[str, str]:
    """The choices a scene's markdown cell ends with, each by the id of the edge
    it follows; none for a cell without them."""
    _, _, written_choices = source.partition(_CHOICES_OPENED)
    choices: dict[str, str] = {}
    for line in written_choices.splitlines():
        choice_written = _CHOICE.match(line)
        if choice_written is None:
            continue
        written_attributes = choice_written.group(1)
        attributes = attributes_in(written_attributes)
        edge_id = attributes[_EDGE]
        choices[edge_id] = choice_written.group(2)
    return choices
