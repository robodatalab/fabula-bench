from tqdm import tqdm

from fabula_bench.benchmark_document import get_choices, get_scene_text, get_tag, tags_meet
from fabula_bench.players.agent_player import AgentPlayer, CompletionModel
from fabula_bench.story_player.exposure_tracker import ExposureTracker
from authordoc.cells.cell import Cell
from authordoc.cells.plot_cell import PlotEdge, PlotNode
from authordoc.cells.salient_concept_cell import SalientConceptCell
from authordoc.iterators.story_words_iterator import StoryWordsIterator
from authordoc.storydoc import Document

STORY_ENDS = "The story ends here."

QUESTION = """In the story you have just played, what is "{title}"? Explain it in \
a few sentences."""


class StoryPlayer:
    """Plays a story scene by scene, from the beginning of the plot at
    `plot_index` among the story's plots: `get_current_scene` tells the current
    scene and its continuations, and `step` follows one of them."""

    def __init__(self, doc: Document, exposure_tracker: ExposureTracker, plot_index: int) -> None:
        self._doc = doc
        self._exposure_tracker = exposure_tracker
        self._plot_index = plot_index
        self.reset()

    def reset(self) -> None:
        """Start the story over, at the beginning of the plot the play starts from."""
        plots = self._doc.plots()
        self._followed_plot = plots[self._plot_index]
        self._current_node = self._followed_plot.nodes[0]

    def step(self, action: int) -> None:
        """Follow the current scene's continuation at index `action`."""
        _, outgoing_edges = self._get_current_scene_nodes()
        edge = outgoing_edges[action]
        self._followed_plot = self._doc.get_plot_of_edge(edge)
        self._current_node = self._followed_plot.get_node_by_id(edge.to_node_id)

    def get_current_scene(self) -> tuple[str, list[str]]:
        """The current scene as the story tells it, up to the gap its
        continuations fill, and those continuations, one for each edge leaving
        it; where the story ends, the scene and no continuations. The scene's
        nodes count as seen by the exposure tracker."""
        current_nodes, outgoing_edges = self._get_current_scene_nodes()
        self._exposure_tracker.see(current_nodes)
        scene_cell = self._get_scene_cell()
        description = get_scene_text(scene_cell.source)
        if not outgoing_edges:
            return (f"{description}\n\n{STORY_ENDS}", [])
        choices = get_choices(scene_cell.source)
        continuations = [choices[edge.edge_id] for edge in outgoing_edges]
        return (description, continuations)

    def _get_current_scene_nodes(self) -> tuple[list[PlotNode], list[PlotEdge]]:
        """The nodes of the current scene — the current node, and every node of the
        other plots whose event meets it — and the edges leaving them."""
        current_tag = get_tag(self._current_node)
        current_nodes = [self._current_node]
        outgoing_edges = [
            edge for edge in self._followed_plot.edges if edge.from_node_id == self._current_node.node_id
        ]
        for plot in self._doc.plots():
            if plot is self._followed_plot:
                continue
            for node in plot.nodes:
                tag = get_tag(node)
                if tags_meet(tag, current_tag):
                    current_nodes.append(node)
                    outgoing_edges += [edge for edge in plot.edges if edge.from_node_id == node.node_id]
        return (current_nodes, outgoing_edges)

    def _get_scene_cell(self) -> Cell:
        """The cell that tells the current scene: the one the current node's words
        are in."""
        first_word = self._current_node.story_word_range.first_word
        story_words = StoryWordsIterator(self._doc)
        scene_word = next(word for word in story_words if word.number == first_word)
        scene_cell = self._doc.cell_with_id(scene_word.cell_id)
        return scene_cell


def play_story(story: Document, evaluated_model: CompletionModel, plot_index: int) -> tuple[list[SalientConceptCell], list[float], list[str]]:
    """The evaluated model plays the story, scene by scene as the story tells it,
    from the beginning of the plot at `plot_index` among the story's plots, then
    explains every salient concept the play showed it, asked by the concept's
    title. Returns those concepts, how much of each the play showed, and the
    model's explanations, in the same order."""
    salient_concepts_tracker = ExposureTracker(story)
    player = StoryPlayer(story, salient_concepts_tracker, plot_index)
    agent = AgentPlayer(evaluated_model)
    agent.play(player)

    concepts = [
        concept for concept in salient_concepts_tracker.concepts if salient_concepts_tracker.get_exposure(concept) > 0
    ]
    exposures = [salient_concepts_tracker.get_exposure(concept) for concept in concepts]
    explanations = []
    concepts_asked = tqdm(concepts, desc="concepts asked", unit="concept")
    for concept in concepts_asked:
        question = QUESTION.format(title=concept.title)
        explanation = agent.ask(question)
        explanations.append(explanation)
    return (concepts, exposures, explanations)
