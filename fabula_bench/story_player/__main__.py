from pathlib import Path

from fabula_bench.story_player.scene_descriptor import SceneDescriptor
from fabula_bench.story_player.story_player import StoryPlayer
from fabula_bench.storydoc.iterators.story_words_iterator import StoryWordsIterator
from fabula_bench.storydoc.storydoc import Document


def main() -> None:
    story = Document.load(Path("fabula_bench/stories/hostage.author"))
    player = StoryPlayer(story)
    story_text = StoryWordsIterator(story)

    scene_descriptor = SceneDescriptor()
    previous_where = None
    previous_scene_texts = None
    while True:
        current_nodes, outgoing_edges, finished = player.get_current_scene()
        if finished:
            break
        scene_texts = [story_text.text(current_node.story_word_range) for current_node in current_nodes]
        scene_tags = [player.get_tag(current_node, story_text) for current_node in current_nodes]
        scene_places = [tag[1] for tag in scene_tags if tag is not None]
        # The scene's nodes meet where the most specific of their places is.
        place = max(scene_places, key=len)
        where = ", ".join(place)
        option_texts = []
        for edge in outgoing_edges:
            edge_plot = player.get_plot_of_edge(edge)
            next_node = edge_plot.get_node_by_id(edge.to_node_id)
            next_text = story_text.text(next_node.story_word_range)
            option_texts.append(next_text)
        description, endings = scene_descriptor.describe(
            where, scene_texts, option_texts, previous_where, previous_scene_texts
        )
        print(description)
        previous_where = where
        previous_scene_texts = scene_texts

        print("\nOptions:")
        for edge_idx, ending in enumerate(endings):
            print(f"  {edge_idx + 1}: {ending}")

        edge_idx = -1
        try:
            edge_idx = int(input("which edge: ")) - 1
        except Exception:
            break

        selected_edge = outgoing_edges[edge_idx]
        player.step(selected_edge)
        print("\n\n----------------\n")

    print("\nExposure to salient concepts:")
    for concept in player.exposure_tracker.concepts:
        seen_references = player.exposure_tracker.get_seen_references(concept)
        exposure = player.exposure_tracker.get_exposure(concept)
        print(f"  {concept.title}: {exposure:.0%} ({len(seen_references)} of {len(concept.references)} references)")



if __name__ == "__main__":
    main()
