import random
import unittest
from unittest.mock import Mock, patch

from authordoc.cells.markdown_cell import MarkdownCell
from authordoc.cells.plot_cell import PlotCell, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell, SalientConceptReference
from authordoc.cells.story_word_range import StoryWordRange
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document
from fabula_bench.interactive_author_story import InteractiveAuthorStory
from story_generator.review import TerminalReview
from story_generator.stages.scenes import SCENE_INSTRUCTIONS, Scenes, SceneStep


class ScenesRun(unittest.TestCase):
    def setUp(self) -> None:
        varn = PlotCell(
            "Motherhood",
            [
                PlotNode("e1", None, "1", "mars, the base", "Dax takes the water from Varn and her son."),
                PlotNode("e2", None, "2", "mars, Varn's room", "Varn shares her water with her son."),
            ],
            [],
            "",
            False,
            None,
            "p1",
        )
        dax = PlotCell(
            "Brutal father",
            [
                PlotNode("f1", None, "1", "mars, the base", "Dax takes the water from Varn and her son."),
                PlotNode("f2", None, "2.5", "mars, the base", "Dax drinks in front of the thirsty."),
            ],
            [],
            "",
            False,
            None,
            "p2",
        )
        self.document = Document.from_cells([varn, dax])
        chance = random.Random(0)
        self.reviews = TerminalReview(0.0, chance)
        self.model = Mock()
        self.model.complete.side_effect = [
            "Dax took the water while Varn held her son close.",
            "Varn gave her son the last cup.\n\nHe drank it slowly.",
            "Dax drank in front of them.",
        ]

    # The author accepts every scene shown.
    @patch("builtins.input", return_value="a")
    def test_every_event_points_at_the_whole_of_its_scene(self, _) -> None:
        where_they_meet, in_varns_room, where_dax_drinks = Scenes(self.model).run(self.document)
        _, with_the_meeting = where_they_meet(self.document, self.reviews, "")
        _, with_varns_room = in_varns_room(with_the_meeting, self.reviews, "")
        _, with_every_scene = where_dax_drinks(with_varns_room, self.reviews, "")

        story_words = StoryWordsIterator(with_every_scene)
        varn, dax = with_every_scene.plots()
        meeting_of_varn, varns_room = varn.nodes
        meeting_of_dax, dax_drinks = dax.nodes
        self.assertEqual(story_words.text(meeting_of_varn.story_word_range), "Dax took the water while Varn held her son close.")
        self.assertEqual(story_words.text(meeting_of_dax.story_word_range), "Dax took the water while Varn held her son close.")
        self.assertEqual(story_words.text(varns_room.story_word_range), "Varn gave her son the last cup.\n\nHe drank it slowly.")
        self.assertEqual(story_words.text(dax_drinks.story_word_range), "Dax drank in front of them.")

    # The author accepts every scene shown.
    @patch("builtins.input", return_value="a")
    def test_every_event_keeps_pointing_at_its_scene_when_a_scene_before_it_grows(self, _) -> None:
        where_they_meet, in_varns_room, where_dax_drinks = Scenes(self.model).run(self.document)
        _, with_the_meeting = where_they_meet(self.document, self.reviews, "")
        _, with_varns_room = in_varns_room(with_the_meeting, self.reviews, "")
        _, with_every_scene = where_dax_drinks(with_varns_room, self.reviews, "")
        story = InteractiveAuthorStory(with_every_scene)
        meeting, _, _ = story.scenes

        # As the choices stage grows a scene: the opening of a sentence it leaves unfinished.
        opened = meeting.with_opening("Varn looked at the door, and then at the window")
        grown = story.with_scenes([opened])

        story_words = StoryWordsIterator(grown.document)
        varn, dax = grown.document.plots()
        meeting_of_varn, varns_room = varn.nodes
        meeting_of_dax, dax_drinks = dax.nodes
        self.assertEqual(story_words.text(meeting_of_varn.story_word_range), "Dax took the water while Varn held her son close.")
        self.assertEqual(story_words.text(meeting_of_dax.story_word_range), "Dax took the water while Varn held her son close.")
        self.assertEqual(story_words.text(varns_room.story_word_range), "Varn gave her son the last cup.\n\nHe drank it slowly.")
        self.assertEqual(story_words.text(dax_drinks.story_word_range), "Dax drank in front of them.")

    # The author accepts the scene shown.
    @patch("builtins.input", return_value="a")
    @patch("builtins.print")
    def test_shows_the_author_where_and_when_the_scene_happens_and_its_events_apart_from_the_scene(self, shown: Mock, _) -> None:
        where_they_meet, _, _ = Scenes(self.model).run(self.document)

        where_they_meet(self.document, self.reviews, "")

        shown.assert_called_once_with(
            "\nWHERE: mars, the base\n"
            "WHEN: 1\n\n"
            "EVENTS:\n"
            '- the event of the plot "Motherhood":\n'
            "  Dax takes the water from Varn and her son.\n"
            '- the event of the plot "Brutal father":\n'
            "  Dax takes the water from Varn and her son.\n\n"
            "SCENE:\n"
            "Dax took the water while Varn held her son close.\n"
        )

    @patch("builtins.input", return_value="a")
    def test_asks_for_the_scene_once_where_events_intersect(self, _) -> None:
        where_they_meet, _, _ = Scenes(self.model).run(self.document)
        where_they_meet(self.document, self.reviews, "")

        self.model.complete.assert_called_once_with(
            SCENE_INSTRUCTIONS,
            "Where: mars, the base\n\nWhat happens:\nDax takes the water from Varn and her son.\n\n",
            3000,
        )


class SceneStepCall(unittest.TestCase):
    # The author accepts the scene shown.
    @patch("builtins.input", return_value="a")
    def test_a_scene_added_to_a_story_that_has_scenes_leaves_every_reference_on_its_words(self, _) -> None:
        # The story's words so far: "The(0) ship(1) landed(2) on(3) Mars(4) at(5)
        # dawn.(6)", the scene of the landing, which the concept points into.
        arrival = SalientConceptCell("Arrival", [SalientConceptReference("r1", StoryWordRange(1, 4))], "", False, None, "k1")
        landing = PlotCell(
            "Arrival",
            [PlotNode("g1", StoryWordRange(0, 6), "0", "mars, the port", "The ship lands.")],
            [],
            "",
            False,
            None,
            "p0",
        )
        varn = PlotCell(
            "Motherhood",
            [PlotNode("e1", None, "1", "mars, the base", "Dax takes the water from Varn and her son.")],
            [],
            "",
            False,
            None,
            "p1",
        )
        dax = PlotCell(
            "Brutal father",
            [PlotNode("f1", None, "1", "mars, the base", "Dax takes the water from Varn and her son.")],
            [],
            "",
            False,
            None,
            "p2",
        )
        the_landing = MarkdownCell("The ship landed on Mars at dawn.", False, None, "s0")
        document = Document.from_cells([arrival, landing, varn, dax, the_landing])
        chance = random.Random(0)
        reviews = TerminalReview(0.0, chance)
        model = Mock()
        model.complete.return_value = "Dax took the water while Varn held her son close."
        where_they_meet = SceneStep(
            [
                PlotNode("e1", None, "1", "mars, the base", "Dax takes the water from Varn and her son."),
                PlotNode("f1", None, "1", "mars, the base", "Dax takes the water from Varn and her son."),
            ],
            model,
        )

        _, with_the_meeting = where_they_meet(document, reviews, "")

        story_words = StoryWordsIterator(with_the_meeting)
        (concept,) = with_the_meeting.salient_concepts()
        (passage,) = concept.references
        landing_plot, varn_plot, dax_plot = with_the_meeting.plots()
        (ship_lands,) = landing_plot.nodes
        (meeting_of_varn,) = varn_plot.nodes
        (meeting_of_dax,) = dax_plot.nodes
        self.assertEqual(story_words.text(passage.story_word_range), "ship landed on Mars")
        self.assertEqual(story_words.text(ship_lands.story_word_range), "The ship landed on Mars at dawn.")
        self.assertEqual(story_words.text(meeting_of_varn.story_word_range), "Dax took the water while Varn held her son close.")
        self.assertEqual(story_words.text(meeting_of_dax.story_word_range), "Dax took the water while Varn held her son close.")
