from vramen import CausalModel

from fabula_bench.benchmark_document import get_place, get_tag, tags_meet
from fabula_bench.players.agent_player import AgentPlayer, CompletionModel
from fabula_bench.story_player.exposure_tracker import ExposureTracker
from fabula_bench.story_player.scene_descriptor import SceneDescriptor
from fabula_bench.storydoc.cells.plot_cell import PlotEdge, PlotNode
from fabula_bench.storydoc.cells.salient_concept_cell import SalientConceptCell
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document

STORY_ENDS = "The story ends here."

QUESTION = """In the story you have just played, what is "{title}"? Explain it in \
a few sentences."""


class StoryPlayer:
    """Plays a story scene by scene: `get_current_scene` tells the current scene
    and its continuations, and `step` follows one of them."""

    def __init__(self, doc: Document, exposure_tracker: ExposureTracker, scene_descriptor: SceneDescriptor) -> None:
        self._doc = doc
        self._exposure_tracker = exposure_tracker
        self._scene_descriptor = scene_descriptor
        self.reset()

    def reset(self) -> None:
        """Start the story over."""
        plots = self._doc.plots()
        self._followed_plot = plots[1]
        self._current_node = self._followed_plot.nodes[0]
        # The nodes of the scene before the current one, which the narrator
        # carries on from; none at the start of the story.
        self._previous_nodes: list[PlotNode] = []

    def step(self, action: int) -> None:
        """Follow the current scene's continuation at index `action`."""
        current_nodes, outgoing_edges = self._get_current_scene_nodes()
        edge = outgoing_edges[action]
        self._previous_nodes = current_nodes
        self._followed_plot = self._doc.get_plot_of_edge(edge)
        self._current_node = self._followed_plot.get_node_by_id(edge.to_node_id)

    def get_current_scene(self) -> tuple[str, list[str]]:
        """The current scene's description as the narrator tells it, and its
        continuations, one for each edge leaving it; no continuations where the
        story ends. The scene's nodes count as seen by the exposure tracker."""
        current_nodes, outgoing_edges = self._get_current_scene_nodes()
        self._exposure_tracker.see(current_nodes)
        if not outgoing_edges:
            return (STORY_ENDS, [])
        next_nodes = []
        for edge in outgoing_edges:
            edge_plot = self._doc.get_plot_of_edge(edge)
            next_node = edge_plot.get_node_by_id(edge.to_node_id)
            next_nodes.append(next_node)
        where = get_place(self._doc, current_nodes)
        scene_texts = self._get_texts(current_nodes)
        option_texts = self._get_texts(next_nodes)
        previous_where = get_place(self._doc, self._previous_nodes) if self._previous_nodes else None
        previous_scene_texts = self._get_texts(self._previous_nodes) if self._previous_nodes else None
        description, continuations = self._scene_descriptor.describe(
            where, scene_texts, option_texts, previous_where, previous_scene_texts
        )
        return (description, continuations)

    def _get_current_scene_nodes(self) -> tuple[list[PlotNode], list[PlotEdge]]:
        """The nodes of the current scene — the current node, and every node of the
        other plots whose event meets it — and the edges leaving them."""
        story_text = StoryWordsIterator(self._doc)
        current_tag = get_tag(self._current_node, story_text)
        current_nodes = [self._current_node]
        outgoing_edges = [
            edge for edge in self._followed_plot.edges if edge.from_node_id == self._current_node.node_id
        ]
        for plot in self._doc.plots():
            if plot is self._followed_plot:
                continue
            for node in plot.nodes:
                tag = get_tag(node, story_text)
                if tags_meet(tag, current_tag):
                    current_nodes.append(node)
                    outgoing_edges += [edge for edge in plot.edges if edge.from_node_id == node.node_id]
        return (current_nodes, outgoing_edges)

    def _get_texts(self, nodes: list[PlotNode]) -> list[str]:
        story_text = StoryWordsIterator(self._doc)
        texts = [story_text.text(node.story_word_range) for node in nodes]
        return texts


def play_story(story: Document, evaluated_model: CompletionModel, narrator_model: CausalModel) -> tuple[list[SalientConceptCell], list[float], list[str]]:
    """The evaluated model plays the story, told scene by scene by the narrator
    model, then explains every salient concept the play showed it, asked by the
    concept's title. Returns those concepts, how much of each the play showed,
    and the model's explanations, in the same order."""
    salient_concepts_tracker = ExposureTracker(story)
    scene_descriptor = SceneDescriptor(narrator_model)
    player = StoryPlayer(story, salient_concepts_tracker, scene_descriptor)
    agent = AgentPlayer(evaluated_model)
    agent.play(player)

    concepts = [
        concept for concept in salient_concepts_tracker.concepts if salient_concepts_tracker.get_exposure(concept) > 0
    ]
    exposures = [salient_concepts_tracker.get_exposure(concept) for concept in concepts]
    explanations = []
    for concept in concepts:
        question = QUESTION.format(title=concept.title)
        explanation = agent.ask(question)
        explanations.append(explanation)
    return (concepts, exposures, explanations)
