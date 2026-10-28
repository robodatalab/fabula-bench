import unittest

from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.plot_cell import PlotCell, PlotEdge, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell, SalientConceptReference
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.benchmark_document import get_choices, get_scene_text
from story_generator.scene_writer import SceneWriter
from story_generator.scenes import scenes_of
from story_generator.story import with_the_choices, with_the_story

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
    [PlotEdge("x1", "a1", "a2")],
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
    [PlotEdge("y1", "b1", "b2"), PlotEdge("y2", "b2", "b3")],
    "A mother leaves.",
    False,
    None,
    "p2",
)
STORY = Document.from_cells([OUTLINE, THE_DISCOVERY, THE_HOUSE])


class _SaysWhatHappens:
    """Stands in for the model: a scene is what happens in it, said back; the
    opening of its unfinished sentence is "Then,", and an ending of it says
    where it leads."""

    def complete(self, system: str, user: str, max_new_tokens: int) -> str:
        if user.startswith("The scene:"):
            return "Then,"
        if user.startswith("The opening:"):
            _, could_happen = user.split("What could happen next:\n")
            return f"towards {could_happen}"
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


class TheChoices(unittest.TestCase):
    def test_end_a_scene_the_story_goes_on_from_one_for_every_edge_leaving_it(self) -> None:
        told = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))

        story = with_the_choices(told, SceneWriter(_SaysWhatHappens()))

        first_scene = story.cells[3]
        scene_text = get_scene_text(first_scene.source)
        choices = get_choices(first_scene.source)
        self.assertEqual(
            scene_text, "The agency broadcasts the find.\nA mother watches the news.\n\nThen, _____"
        )
        self.assertEqual(
            choices,
            {
                "x1": "towards 1.2. [mars] Robots dig.",
                "y1": "towards 1.2. [earth, the base] She is given a ship.",
            },
        )

    def test_leave_a_scene_the_story_ends_in_as_it_was(self) -> None:
        told = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))

        story = with_the_choices(told, SceneWriter(_SaysWhatHappens()))

        scenes_ending_the_story = [story.cells[4].source, story.cells[6].source]
        self.assertEqual(scenes_ending_the_story, ["Robots dig.", "She reaches Mars."])

    def test_leave_every_event_and_concept_pointed_at_the_words_it_had(self) -> None:
        told = with_the_story(STORY, SceneWriter(_SaysWhatHappens()))
        _, house_told = told.plots()
        _, b2_told, _ = house_told.nodes
        reference = SalientConceptReference("r1", b2_told.story_word_range)
        leaving = SalientConceptCell(title="Leaving", references=[reference], source="Leaving home.")
        told_with_a_concept = Document.from_cells([*told.cells, leaving])

        story = with_the_choices(told_with_a_concept, SceneWriter(_SaysWhatHappens()))

        words = StoryWordsIterator(story)
        _, house = story.plots()
        _, b2, _ = house.nodes
        (leaving_now,) = story.salient_concepts()
        b2_words = words.text(b2.story_word_range)
        leaving_words = words.text(leaving_now.references[0].story_word_range)
        self.assertNotEqual(b2.story_word_range, b2_told.story_word_range)
        self.assertEqual(b2_words, "She is given a ship.")
        self.assertEqual(leaving_words, "She is given a ship.")
