import unittest

from fabula_bench.storydoc.cells.markdown_cell import MarkdownCell
from fabula_bench.storydoc.cells.plot_cell import PlotCell, PlotNode
from fabula_bench.storydoc.cells.story_word_range import StoryWordRange
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document
from story_generator.scene_writer import SceneWriter
from story_generator.scenes import scenes_of
from story_generator.story import with_the_story

# Two plots on one clock: at 1.1 the broadcast is seen in the house it reaches;
# at 1.2 the plots part, one on Mars and one at the base; an event with no
# moment or place belongs to no scene.
OUTLINE = MarkdownCell(source="A probe finds something. The house watches.", _unique_id="m1")
THE_DISCOVERY = PlotCell(
    "The discovery",
    [
        PlotNode("a1", StoryWordRange(0, 3), "1.1", "earth", "The agency broadcasts the find."),
        PlotNode("a2", None, "1.2", "mars", "Robots dig."),
        PlotNode("a3", None, "", "", "Somewhere, someone wonders."),
    ],
    [],
    "What was found.",
    False,
    None,
    "p1",
)
THE_HOUSE = PlotCell(
    "The house",
    [
        PlotNode("b1", StoryWordRange(4, 6), "1.1", "earth, the house", "A mother watches the news."),
        PlotNode("b2", None, "1.2", "earth, the base", "She is given a ship."),
        PlotNode("b3", None, "1.10", "orbit", "She reaches Mars."),
    ],
    [],
    "A mother leaves.",
    False,
    None,
    "p2",
)
STORY = Document.from_cells([OUTLINE, THE_DISCOVERY, THE_HOUSE])


class _SaysWhatHappens:
    """Stands in for the model: a scene is what happens in it, said back."""

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        _, happening = user.split("What happens there:\n")
        return happening.replace("- ", "")


class Scenes(unittest.TestCase):
    def test_group_the_events_that_meet_in_the_order_of_the_clock(self) -> None:
        scenes = scenes_of(STORY)

        ids_of_each_scene = [[event.node_id for event in scene] for scene in scenes]
        self.assertEqual(ids_of_each_scene, [["a1", "b1"], ["a2"], ["b2"], ["b3"]])


class TheStory(unittest.TestCase):
    def test_is_a_scene_for_each_group_of_events_after_every_cell_there_was(self) -> None:
        story = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))

        scenes_written = [cell.source for cell in story.cells[3:]]
        self.assertEqual([cell.unique_id for cell in story.cells[:3]], ["m1", "p1", "p2"])
        self.assertEqual(
            scenes_written,
            [
                "The agency broadcasts the find.\nA mother watches the news.",
                "Robots dig.",
                "She is given a ship.",
                "She reaches Mars.",
            ],
        )

    def test_points_every_event_of_a_scene_at_the_scene_and_leaves_the_rest(self) -> None:
        story = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))

        discovery, house = story.plots()
        words = StoryWordsIterator(story)
        a1, a2, a3 = discovery.nodes
        b1, _, _ = house.nodes
        self.assertEqual(a1.story_word_range, b1.story_word_range)
        self.assertEqual(
            words.text(a1.story_word_range),
            "The agency broadcasts the find.\nA mother watches the news.",
        )
        self.assertEqual(words.text(a2.story_word_range), "Robots dig.")
        self.assertIsNone(a3.story_word_range)

    def test_moves_no_word_the_document_had(self) -> None:
        story = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))

        words_before = [(word.number, word.text) for word in StoryWordsIterator(STORY)]
        words_after = [(word.number, word.text) for word in StoryWordsIterator(story)]
        self.assertEqual(words_after[: len(words_before)], words_before)
